"""Minimal JSON server for the ShriTeq TUI viewer.

The dashboard payload is expensive to build (a full MPC+PPO benchmark, minutes),
so it is computed once at startup into a module-level cache and served instantly
at ``GET /api/dashboard``. Run on a main device:

    .venv/bin/python -m shriteq.app.server --host 0.0.0.0 --port 8000

An optional ``--refresh-secs`` rebuilds the cache periodically in the background.
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shriteq.config import SiteConfig
from shriteq.app.payload import build_dashboard_payload

_CACHE_LOCK = threading.Lock()
_CACHED_JSON: bytes = b"{}"


def _rebuild_cache(config: SiteConfig, seed: int) -> None:
    global _CACHED_JSON
    print("building dashboard payload (this runs a full benchmark)...", flush=True)
    payload = build_dashboard_payload(config, seed)
    encoded = json.dumps(payload).encode("utf-8")
    with _CACHE_LOCK:
        _CACHED_JSON = encoded
    print(f"payload ready ({len(encoded)} bytes)", flush=True)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path.split("?", 1)[0] != "/api/dashboard":
            self.send_error(404, "not found")
            return
        with _CACHE_LOCK:
            body = _CACHED_JSON
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep the console quiet
        return


def _schedule_refresh(config: SiteConfig, seed: int, refresh_secs: float) -> None:
    def _tick() -> None:
        _rebuild_cache(config, seed)
        _schedule_refresh(config, seed, refresh_secs)

    timer = threading.Timer(refresh_secs, _tick)
    timer.daemon = True
    timer.start()


def main() -> None:
    parser = argparse.ArgumentParser(description="ShriTeq TUI JSON server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--refresh-secs",
        type=float,
        default=0.0,
        help="rebuild the payload every N seconds (0 = build once at startup)",
    )
    args = parser.parse_args()

    config = SiteConfig()
    _rebuild_cache(config, args.seed)
    if args.refresh_secs > 0:
        _schedule_refresh(config, args.seed, args.refresh_secs)

    server = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"serving /api/dashboard on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
