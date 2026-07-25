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

### GPIO buttons (Raspberry Pi)

Physical push-buttons can switch screens in addition to the number keys. Wire
each button between a **BCM pin** and **ground** (the internal pull-up makes a
press read active-low), then enable it in `config.toml`:

```toml
[gpio]
enabled = true
poll_ms = 10       # pin poll interval
debounce_ms = 50   # ignore repeats within this window

[[gpio.button]]
pin = 20           # BCM pin
action = "next"    # "next", "prev", or a 1-based screen number ("1".."4")
```

`action` values: `next`/`prev` cycle through the four screens; `"1"`..`"4"` jump
directly (Dashboard/Live/Graph/QR). GPIO is Linux-only and a no-op elsewhere, so
the macOS dev build is unaffected. The Pi target is
`arm-unknown-linux-gnueabihf` (see `.cargo/config.toml`).

#### Buttons not working? Run the diagnostic

The GPIO thread runs in the background under the TUI, so its errors aren't
visible on screen. Diagnose without the TUI:

```bash
./tui_viewer --gpio-test        # add --config <path> if config.toml isn't in cwd
```

It prints the loaded GPIO config, opens the pins, shows each pin's idle level,
then streams every change as you press. Common causes it pins down:

- **GPIO disabled / config not found** — the summary shows `gpio.enabled` and
  the button count. On boot the app also logs its config source to stderr:
  `config: source=... gpio.enabled=... gpio.buttons=...`. If it says "no
  config.toml found", you're running from a directory without one — the app now
  also looks next to the binary, or pass `--config`. **Set `enabled = true`.**
- **Permissions** — `Gpio::new() failed` usually means your user isn't in the
  `gpio` group: `sudo usermod -aG gpio $USER`, then log out/in (or run with
  `sudo`). Background-run errors are also appended to
  `$TMPDIR/tui_viewer_gpio.log` (usually `/tmp/tui_viewer_gpio.log`).
- **Wiring** — idle level should read **HIGH**; the button connects the pin to
  **GND** (the internal pull-up does the rest). If the diagnostic shows the pin
  already **LOW** at idle, it's likely wired to 3V3 instead of ground, or the
  `pin` number is the physical header number, not the **BCM** number.
- **`pin` is BCM, not board** — e.g. BCM 20 is physical header pin 38.

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
  event.rs           input + tick event loop (shared channel)
  gpio.rs            Raspberry Pi push-buttons -> screen-switch events (Linux only)
  config.rs          config.toml + 3 QR slots + [gpio]
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
