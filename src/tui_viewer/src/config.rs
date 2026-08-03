//! Viewer configuration: server URL, refresh cadence, and the three QR slots.

use std::path::Path;

use serde::Deserialize;

pub const QR_SLOTS: usize = 2;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    #[serde(default = "default_server")]
    pub server_url: String,
    #[serde(default = "default_refresh")]
    pub refresh_secs: u64,
    #[serde(default)]
    pub qr: Vec<QrEntry>,
    #[serde(default)]
    pub gpio: GpioConfig,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct QrEntry {
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub url: String,
}

/// GPIO push-button configuration (Raspberry Pi). Buttons are wired to a BCM
/// pin and ground, read active-low with the internal pull-up. Disabled by
/// default and a no-op on non-Linux hosts, so the dev build is unaffected.
// The GPIO fields are only read in the Linux (rppal) code path; suppress the
// dead-code lint on non-Linux hosts where `gpio::spawn` is a no-op.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
#[derive(Debug, Clone, Deserialize)]
pub struct GpioConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_poll_ms")]
    pub poll_ms: u64,
    #[serde(default = "default_debounce_ms")]
    pub debounce_ms: u64,
    #[serde(default)]
    pub button: Vec<ButtonConfig>,
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
#[derive(Debug, Clone, Deserialize)]
pub struct ButtonConfig {
    /// BCM pin number the button is wired to (other side to ground).
    pub pin: u8,
    /// "next", "prev", or a 1-based screen number ("1".."4").
    pub action: String,
}

impl Default for GpioConfig {
    fn default() -> Self {
        GpioConfig {
            enabled: false,
            poll_ms: default_poll_ms(),
            debounce_ms: default_debounce_ms(),
            button: Vec::new(),
        }
    }
}

fn default_poll_ms() -> u64 {
    10
}

fn default_debounce_ms() -> u64 {
    50
}

fn default_server() -> String {
    "http://127.0.0.1:8000".to_string()
}

fn default_refresh() -> u64 {
    30
}

impl Default for Config {
    fn default() -> Self {
        Config {
            server_url: default_server(),
            refresh_secs: default_refresh(),
            qr: Vec::new(),
            gpio: GpioConfig::default(),
        }
        .normalized()
    }
}

impl Config {
    /// Load from `path` if given, else `./config.toml`, else `config.toml` next
    /// to the executable, else defaults. A found-but-unparseable file logs a
    /// clear warning instead of silently falling back (which would disable
    /// GPIO). Always normalized to exactly `QR_SLOTS` slots.
    pub fn load(path: Option<&Path>) -> Self {
        let resolved = path
            .map(Path::to_path_buf)
            .or_else(|| existing(Path::new("config.toml")))
            .or_else(exe_dir_config);

        let cfg = match &resolved {
            Some(p) => match std::fs::read_to_string(p) {
                Ok(text) => match toml::from_str::<Config>(&text) {
                    Ok(cfg) => cfg,
                    Err(err) => {
                        eprintln!(
                            "config: failed to parse {}: {err}; using defaults",
                            p.display()
                        );
                        Config::default()
                    }
                },
                Err(err) => {
                    eprintln!(
                        "config: failed to read {}: {err}; using defaults",
                        p.display()
                    );
                    Config::default()
                }
            },
            None => {
                eprintln!(
                    "config: no config.toml found in the working directory or next to the \
                     binary; using defaults (GPIO disabled). Pass --config <path> to point at one."
                );
                Config::default()
            }
        };
        eprintln!(
            "config: source={:?} gpio.enabled={} gpio.buttons={}",
            resolved.as_deref(),
            cfg.gpio.enabled,
            cfg.gpio.button.len(),
        );
        cfg.normalized()
    }

    fn normalized(mut self) -> Self {
        while self.qr.len() < QR_SLOTS {
            self.qr.push(QrEntry::default());
        }
        self.qr.truncate(QR_SLOTS);
        self
    }
}

fn existing(path: &Path) -> Option<std::path::PathBuf> {
    path.exists().then(|| path.to_path_buf())
}

/// `config.toml` sitting next to the executable (covers running the binary from
/// a different working directory, e.g. a systemd service on the Pi).
fn exe_dir_config() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let candidate = exe.parent()?.join("config.toml");
    existing(&candidate)
}
