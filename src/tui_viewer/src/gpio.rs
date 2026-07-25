//! GPIO push-button input for switching screens on a Raspberry Pi.
//!
//! Buttons are wired between a BCM pin and ground and read active-low with the
//! internal pull-up (idle High, pressed Low), mirroring the reference design in
//! `gdgps_interschool`. A background thread polls the pins with debouncing and
//! forwards presses as [`Event::Gpio`] on the shared event channel.
//!
//! The real implementation is Linux-only (rppal); on other hosts `spawn` is a
//! no-op so the macOS dev build works unchanged.

use std::sync::Arc;
use std::sync::atomic::AtomicBool;
use std::sync::mpsc::Sender;

use crate::config::GpioConfig;
use crate::event::{Event, GpioAction};

/// Parse a config action string into a [`GpioAction`].
///
/// Accepts `"next"`, `"prev"`/`"previous"`/`"back"`, or a 1-based screen number
/// (`"1"`..`"4"`) which maps to a 0-based [`GpioAction::Screen`].
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
fn parse_action(spec: &str) -> Option<GpioAction> {
    match spec.trim().to_ascii_lowercase().as_str() {
        "next" => Some(GpioAction::Next),
        "prev" | "previous" | "back" => Some(GpioAction::Prev),
        other => other
            .parse::<usize>()
            .ok()
            .and_then(|n| n.checked_sub(1))
            .map(GpioAction::Screen),
    }
}

/// Spawn the GPIO watcher. Returns an `active` flag the UI can poll: it becomes
/// `true` once the pins are open and being read, and stays `false` if GPIO is
/// disabled, misconfigured, or fails to initialise. Reasons are appended to the
/// log at `$TMPDIR/tui_viewer_gpio.log`.
#[cfg(target_os = "linux")]
pub fn spawn(tx: Sender<Event>, config: GpioConfig) -> Arc<AtomicBool> {
    use std::sync::atomic::Ordering;
    use std::thread;
    use std::time::{Duration, Instant};

    use rppal::gpio::{Gpio, InputPin, Level};

    let active = Arc::new(AtomicBool::new(false));

    if !config.enabled {
        log_line("not started: [gpio] enabled = false in config.toml");
        return active;
    }
    let buttons: Vec<(u8, GpioAction)> = config
        .button
        .iter()
        .filter_map(|b| parse_action(&b.action).map(|action| (b.pin, action)))
        .collect();
    if buttons.is_empty() {
        log_line("not started: no valid [[gpio.button]] entries (check pin/action)");
        return active;
    }
    let poll = Duration::from_millis(config.poll_ms.max(1));
    let debounce = Duration::from_millis(config.debounce_ms);
    let active_thread = active.clone();

    thread::spawn(move || {
        let gpio = match Gpio::new() {
            Ok(gpio) => gpio,
            Err(err) => {
                // stderr is invisible under the TUI's alternate screen, so also
                // persist to a log file the user can inspect after the fact.
                log_line(&format!(
                    "Gpio::new() failed: {err}. Is your user in the 'gpio' group \
                     (or running as root), and does /dev/gpiomem exist? \
                     Try `tui_viewer --gpio-test`."
                ));
                return;
            }
        };
        // (pin, action, previous level, last-press instant)
        let mut pins: Vec<(InputPin, GpioAction, Level, Instant)> = Vec::new();
        for (pin, action) in buttons {
            match gpio.get(pin) {
                Ok(pin) => {
                    pins.push((pin.into_input_pullup(), action, Level::High, Instant::now()))
                }
                Err(err) => log_line(&format!("skipping pin: {err}")),
            }
        }
        if pins.is_empty() {
            log_line("not started: no pins could be opened");
            return;
        }
        active_thread.store(true, Ordering::Relaxed);
        log_line(&format!("watching {} pin(s)", pins.len()));
        loop {
            for (pin, action, prev, last_press) in pins.iter_mut() {
                let current = pin.read();
                // Falling edge (High -> Low) is a press; debounce repeats.
                if *prev == Level::High && current == Level::Low && last_press.elapsed() >= debounce
                {
                    if tx.send(Event::Gpio(*action)).is_err() {
                        return;
                    }
                    *last_press = Instant::now();
                }
                *prev = current;
            }
            thread::sleep(poll);
        }
    });
    active
}

#[cfg(not(target_os = "linux"))]
pub fn spawn(_tx: Sender<Event>, _config: GpioConfig) -> Arc<AtomicBool> {
    // GPIO is only available on the Raspberry Pi (Linux); no-op elsewhere.
    Arc::new(AtomicBool::new(false))
}

/// Append a line to a persistent GPIO log (stderr is hidden under the TUI).
#[cfg(target_os = "linux")]
fn log_line(msg: &str) {
    use std::io::Write;
    let path = std::env::temp_dir().join("tui_viewer_gpio.log");
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
    {
        let _ = writeln!(file, "gpio: {msg}");
    }
    eprintln!("gpio: {msg}");
}

/// Interactive diagnostic (run with `--gpio-test`): print config, initialise the
/// configured pins, and stream every level change so wiring/permissions/config
/// can be verified without launching the TUI. Ignores `enabled`.
#[cfg(target_os = "linux")]
pub fn diagnose(config: &GpioConfig) -> anyhow::Result<()> {
    use std::thread;
    use std::time::Duration;

    use rppal::gpio::{Gpio, Level};

    println!("GPIO diagnostic");
    println!("  enabled     = {}", config.enabled);
    println!("  poll_ms     = {}", config.poll_ms);
    println!("  debounce_ms = {}", config.debounce_ms);
    if !config.enabled {
        println!(
            "  WARNING: enabled = false — this test still runs, but the main app will NOT \
             start GPIO. Set `enabled = true` under [gpio] in config.toml."
        );
    }
    if config.button.is_empty() {
        println!(
            "  no [[gpio.button]] entries found — add one (pin + action) to config.toml \
             and pass --config if it isn't in the working directory."
        );
        return Ok(());
    }

    let gpio = Gpio::new().map_err(|err| {
        anyhow::anyhow!(
            "Gpio::new() failed: {err}\n  \
             - is /dev/gpiomem present?\n  \
             - is your user in the 'gpio' group? (`sudo usermod -aG gpio $USER`, then re-login)\n  \
             - or run this test with sudo"
        )
    })?;

    let mut pins = Vec::new();
    for button in &config.button {
        let action = parse_action(&button.action);
        let pin = gpio
            .get(button.pin)
            .map_err(|err| anyhow::anyhow!("get BCM pin {}: {err}", button.pin))?
            .into_input_pullup();
        let level = pin.read();
        let hint = if level == Level::Low {
            "  <-- already LOW at idle; wire the button between this pin and GND (not 3V3)"
        } else {
            "  (HIGH = idle, good)"
        };
        println!(
            "  BCM pin {} -> action {:?}; initial level {:?}{hint}",
            button.pin, action, level
        );
        pins.push((button.pin, pin, level, action));
    }

    println!("\nPress your button(s) now — each change prints below. Ctrl-C to stop.\n");
    let poll = Duration::from_millis(config.poll_ms.max(1));
    loop {
        for (bcm, pin, prev, action) in pins.iter_mut() {
            let current = pin.read();
            if current != *prev {
                let edge = if *prev == Level::High && current == Level::Low {
                    "  <== PRESS"
                } else {
                    ""
                };
                println!(
                    "pin {bcm}: {:?} -> {:?}{edge}  (action {:?})",
                    *prev, current, action
                );
                *prev = current;
            }
        }
        thread::sleep(poll);
    }
}

#[cfg(not(target_os = "linux"))]
pub fn diagnose(_config: &GpioConfig) -> anyhow::Result<()> {
    println!("GPIO is only available on Linux (Raspberry Pi); nothing to test here.");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_actions() {
        assert_eq!(parse_action("next"), Some(GpioAction::Next));
        assert_eq!(parse_action(" Prev "), Some(GpioAction::Prev));
        assert_eq!(parse_action("back"), Some(GpioAction::Prev));
        assert_eq!(parse_action("1"), Some(GpioAction::Screen(0)));
        assert_eq!(parse_action("4"), Some(GpioAction::Screen(3)));
        assert_eq!(parse_action("0"), None);
        assert_eq!(parse_action("nope"), None);
    }
}
