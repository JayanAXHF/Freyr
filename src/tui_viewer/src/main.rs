//! ShriTeq GridEdge TUI viewer — a Ratatui dashboard sized for a 3.5" display.

mod app;
mod config;
mod data;
mod event;
mod ui;

use std::path::PathBuf;

use anyhow::Result;
use clap::Parser;
use ratatui::DefaultTerminal;

use app::App;
use config::Config;
use data::DataSource;
use event::Event;

/// Animation / channel-drain cadence.
const TICK_MS: u64 = 250;

#[derive(Parser)]
#[command(name = "tui_viewer", about = "ShriTeq GridEdge TUI viewer")]
struct Args {
    /// Server base URL (overrides config.toml).
    #[arg(long)]
    server: Option<String>,
    /// Load a static snapshot file instead of polling the server.
    #[arg(long)]
    snapshot: Option<PathBuf>,
    /// Path to a config.toml (defaults to ./config.toml).
    #[arg(long)]
    config: Option<PathBuf>,
    /// Validate the data source (fetch/parse once, print a summary) and exit —
    /// no TUI. Useful for CI and checking the server contract.
    #[arg(long)]
    check: bool,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let mut config = Config::load(args.config.as_deref());
    if let Some(server) = args.server {
        config.server_url = server;
    }

    if args.check {
        return check(&config, args.snapshot.as_deref());
    }

    let source = match args.snapshot {
        Some(path) => DataSource::Snapshot { path },
        None => DataSource::Server {
            base_url: config.server_url.clone(),
            refresh_secs: config.refresh_secs,
        },
    };

    let data_rx = data::spawn(source);
    let event_rx = event::spawn(TICK_MS);

    let mut terminal = ratatui::init();
    let mut app = App::new(config, data_rx);
    let result = run(&mut terminal, &mut app, event_rx);
    ratatui::restore();
    result
}

/// Fetch/parse the data source once and print a summary, without a TUI.
fn check(config: &Config, snapshot: Option<&std::path::Path>) -> Result<()> {
    let snap = match snapshot {
        Some(path) => data::client::load_snapshot(path)?,
        None => data::client::fetch(&config.server_url)?,
    };
    println!(
        "ok: seed={} forecast_pts={} trace_pts={} mpc_bill={:.0} learned_bill={:.0} savings={}",
        snap.seed,
        snap.forecast.len(),
        snap.trace.len(),
        snap.benchmark.mpc.total_bill,
        snap.benchmark.learned.total_bill,
        snap.benchmark
            .learned
            .savings_pct
            .map(|p| format!("{p:.1}%"))
            .unwrap_or_else(|| "n/a".to_string()),
    );
    Ok(())
}

fn run(
    terminal: &mut DefaultTerminal,
    app: &mut App,
    event_rx: std::sync::mpsc::Receiver<Event>,
) -> Result<()> {
    while !app.should_quit {
        terminal.draw(|frame| ui::draw(frame, app))?;
        match event_rx.recv() {
            Ok(event) => app.on_event(event),
            Err(_) => break,
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::app::Screen;
    use crate::data::model::Snapshot;
    use ratatui::Terminal;
    use ratatui::backend::TestBackend;
    use std::sync::mpsc;

    fn sample() -> Snapshot {
        serde_json::from_str(include_str!("../tests/sample_snapshot.json"))
            .expect("sample snapshot parses")
    }

    fn app_with(snapshot: Option<Snapshot>, screen: Screen) -> App {
        let (_tx, rx) = mpsc::channel();
        let mut app = App::new(Config::default(), rx);
        app.snapshot = snapshot;
        app.screen = screen;
        app
    }

    fn draw(app: &App, w: u16, h: u16) {
        let mut terminal = Terminal::new(TestBackend::new(w, h)).unwrap();
        terminal.draw(|frame| ui::draw(frame, app)).unwrap();
    }

    #[test]
    fn sample_snapshot_shape() {
        let snap = sample();
        assert_eq!(snap.forecast.len(), 96);
        assert!(!snap.trace.is_empty());
        assert!(snap.benchmark.learned.savings_pct.unwrap() > 0.0);
    }

    #[test]
    fn renders_all_screens_at_kiosk_size() {
        let snap = sample();
        for screen in [
            Screen::DashboardStatic,
            Screen::DashboardLive,
            Screen::Graph,
            Screen::Qr,
        ] {
            draw(&app_with(Some(snap.clone()), screen), 55, 20);
        }
    }

    #[test]
    fn renders_without_data_and_when_too_small() {
        let app = app_with(None, Screen::DashboardStatic);
        draw(&app, 55, 20); // "waiting for data"
        draw(&app, 20, 8); // too-small guard
    }

    #[test]
    fn config_normalizes_to_three_qr_slots() {
        assert_eq!(Config::default().qr.len(), crate::config::QR_SLOTS);
    }
}
