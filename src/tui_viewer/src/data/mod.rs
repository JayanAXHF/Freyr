//! Data layer: a background thread polls the server (or loads a snapshot once)
//! and streams results to the app over an mpsc channel.

pub mod client;
pub mod model;

use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver};
use std::thread;
use std::time::Duration;

use model::Snapshot;

pub enum DataSource {
    Server { base_url: String, refresh_secs: u64 },
    Snapshot { path: PathBuf },
}

/// Connection status shown in the title/status bars.
#[derive(Debug, Clone)]
pub enum ConnState {
    Connecting,
    Ok,
    Error(String),
}

pub enum DataMsg {
    Snapshot(Box<Snapshot>),
    Error(String),
}

/// Spawn the data thread and return the receiving end.
pub fn spawn(source: DataSource) -> Receiver<DataMsg> {
    let (tx, rx) = mpsc::channel();
    thread::spawn(move || match source {
        DataSource::Server {
            base_url,
            refresh_secs,
        } => loop {
            let msg = match client::fetch(&base_url) {
                Ok(snapshot) => DataMsg::Snapshot(Box::new(snapshot)),
                Err(err) => DataMsg::Error(err.to_string()),
            };
            if tx.send(msg).is_err() {
                break;
            }
            thread::sleep(Duration::from_secs(refresh_secs.max(1)));
        },
        DataSource::Snapshot { path } => {
            let msg = match client::load_snapshot(&path) {
                Ok(snapshot) => DataMsg::Snapshot(Box::new(snapshot)),
                Err(err) => DataMsg::Error(err.to_string()),
            };
            let _ = tx.send(msg);
        }
    });
    rx
}
