//! Input + tick event loop. Emits key/resize events and a periodic tick used to
//! drive the animation and drain the data channel.

use std::sync::mpsc::Sender;
use std::thread;
use std::time::Duration;

use ratatui::crossterm::event::{self, Event as CtEvent, KeyEvent};

pub enum Event {
    Key(KeyEvent),
    Tick,
    /// Terminal resize; the payload is unused today but a resize still forces a
    /// redraw via the main loop.
    Resize(#[allow(dead_code)] u16, #[allow(dead_code)] u16),
    /// A GPIO push-button press mapped to a screen action. Only constructed on
    /// Linux (Raspberry Pi); the variant is still handled on every platform.
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    Gpio(GpioAction),
}

/// What a GPIO button does when pressed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GpioAction {
    /// Cycle to the next screen.
    Next,
    /// Cycle to the previous screen.
    Prev,
    /// Jump to a specific screen by 0-based index.
    Screen(usize),
}

/// Spawn the terminal-input thread. `tick_ms` is the animation/refresh cadence.
/// Events are sent on the shared `tx` (also used by the GPIO thread).
pub fn spawn(tx: Sender<Event>, tick_ms: u64) {
    thread::spawn(move || {
        let tick = Duration::from_millis(tick_ms);
        loop {
            let ready = event::poll(tick).unwrap_or(false);
            if ready {
                match event::read() {
                    Ok(CtEvent::Key(key)) => {
                        if tx.send(Event::Key(key)).is_err() {
                            break;
                        }
                    }
                    Ok(CtEvent::Resize(w, h)) => {
                        if tx.send(Event::Resize(w, h)).is_err() {
                            break;
                        }
                    }
                    Ok(_) => {}
                    Err(_) => break,
                }
            } else if tx.send(Event::Tick).is_err() {
                break;
            }
        }
    });
}
