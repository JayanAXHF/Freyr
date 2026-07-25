# tui_viewer — ShriTeq GridEdge TUI

A Ratatui terminal dashboard for the GridEdge demo, sized for a **3.5" display**
(~55×20 cells). It mirrors the Streamlit dashboard and adds an animated playback
and a QR-code screen for a booth/kiosk.

## Screens

Switch with `1` / `2` / `3` / `4`:

1. **Dashboard** — "Now" tiles, the next-24h load/solar/grid chart, and the
   MPC-vs-learned benchmark table.
2. **Live** — animated playback of the 30-day dispatch trace with a moving
   cursor; tiles and the rolling billing peak update on a timer.
   `space` pauses/resumes, `r` restarts the sweep.
3. **Graph** — the next-24h chart on its own, full-screen. The dashboard layout
   squeezes the chart on a small (3.5") display; this screen gives it the whole
   area.
4. **QR** — three configurable resource slots; `j`/`k` (or ↑/↓) selects one and
   renders its QR code.

`q` / `Esc` quits.

## Data source

The TUI is an HTTP client. Data comes from a small server on a main device
(Streamlit-style), or from a static JSON snapshot.

**Server mode (default):**

```bash
# on the main device (runs the benchmark once, then serves the cached JSON)
.venv/bin/python -m shriteq.app.server --host 0.0.0.0 --port 8000

# on the kiosk
cargo run -- --server http://<main-device>:8000
```

**Snapshot mode (offline):**

```bash
# export a snapshot (git-ignored) — runs the full benchmark
.venv/bin/python scripts/export_tui_snapshot.py            # -> src/tui_viewer/data/snapshot.json
cargo run -- --snapshot data/snapshot.json
```

**Validate a source without launching the TUI** (CI / contract check):

```bash
cargo run -- --snapshot data/snapshot.json --check
cargo run -- --server http://127.0.0.1:8000 --check
```

## Configuration

`config.toml` (next to the binary, or `--config <path>`):

```toml
server_url  = "http://127.0.0.1:8000"
refresh_secs = 30

[[qr]]                       # slot 1
label = "GitHub repo"
url   = "https://github.com/JayanAXHF/lvis_shriteq_26"

[[qr]]                       # slot 2 (fill in)
label = ""
url   = ""

[[qr]]                       # slot 3 (fill in)
label = ""
url   = ""
```

CLI flags override config: `--server`, `--snapshot`, `--config`.

## Layout

```
src/
  main.rs            entry: args, terminal init/restore, main loop, --check
  app.rs             App state, Screen enum, key/tick handling
  event.rs           input + tick event loop
  config.rs          config.toml + 3 QR slots
  data/              model.rs (wire types), client.rs (ureq/file), mod.rs (bg thread)
  ui/
    mod.rs           top-level draw + min-size guard
    theme.rs         palette
    layout.rs        split helpers
    components/      title_bar, status_bar, now_tiles, forecast_chart,
                     benchmark_table, qr_panel  (one file per widget)
    screens/         dashboard_static, dashboard_live, graph, qr
```

## Develop

```bash
cargo fmt
cargo clippy --all --workspace
cargo test --all --workspace
```
