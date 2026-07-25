"""Export a static dashboard snapshot for the TUI viewer's --snapshot mode.

    .venv/bin/python scripts/export_tui_snapshot.py [output_path]

Writes the same payload the server serves to a JSON file (default
``src/tui_viewer/data/snapshot.json``, which is git-ignored).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shriteq.config import SiteConfig
from shriteq.app.payload import build_dashboard_payload

DEFAULT_OUTPUT = Path("src/tui_viewer/data/snapshot.json")


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    print("building dashboard payload (this runs a full benchmark)...", flush=True)
    payload = build_dashboard_payload(SiteConfig())
    output.write_text(json.dumps(payload, indent=2))
    print(f"wrote snapshot -> {output}", flush=True)


if __name__ == "__main__":
    main()
