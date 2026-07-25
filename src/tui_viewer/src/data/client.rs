//! Fetch the dashboard snapshot from the server or a static file.

use std::path::Path;

use anyhow::{Context, Result};

use super::model::Snapshot;

/// GET `{base_url}/api/dashboard` and parse it into a [`Snapshot`].
pub fn fetch(base_url: &str) -> Result<Snapshot> {
    let url = format!("{}/api/dashboard", base_url.trim_end_matches('/'));
    let mut response = ureq::get(&url)
        .call()
        .with_context(|| format!("GET {url}"))?;
    let snapshot = response
        .body_mut()
        .read_json::<Snapshot>()
        .context("parse dashboard JSON")?;
    Ok(snapshot)
}

/// Load a static snapshot JSON file (for `--snapshot`).
pub fn load_snapshot(path: &Path) -> Result<Snapshot> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let snapshot = serde_json::from_str(&text).context("parse snapshot JSON")?;
    Ok(snapshot)
}
