//! Viewer configuration: server URL, refresh cadence, and the three QR slots.

use std::path::Path;

use serde::Deserialize;

pub const QR_SLOTS: usize = 3;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    #[serde(default = "default_server")]
    pub server_url: String,
    #[serde(default = "default_refresh")]
    pub refresh_secs: u64,
    #[serde(default)]
    pub qr: Vec<QrEntry>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct QrEntry {
    #[serde(default)]
    pub label: String,
    #[serde(default)]
    pub url: String,
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
        }
        .normalized()
    }
}

impl Config {
    /// Load from `path` if given, else from `config.toml` next to the binary's
    /// working dir, else defaults. Always normalized to exactly `QR_SLOTS` slots.
    pub fn load(path: Option<&Path>) -> Self {
        let candidate = path.map(Path::to_path_buf).or_else(|| {
            let default = Path::new("config.toml");
            default.exists().then(|| default.to_path_buf())
        });
        let cfg = candidate
            .and_then(|p| std::fs::read_to_string(p).ok())
            .and_then(|text| toml::from_str::<Config>(&text).ok())
            .unwrap_or_default();
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
