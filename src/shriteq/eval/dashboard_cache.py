"""On-disk cache contract shared by the precompute script and the dashboard.

The dashboard used to run a full 30-day forecast-driven benchmark on every page
load (two SARIMAX fits, ~360 MPC solves, a 2880-step PPO rollout), which made a
cold ``streamlit run`` take minutes. This module moves that cost offline: a
precompute step runs the benchmark once and persists the result here, and the
dashboard just reads the four files back. Both sides import the paths/schema
from this module so they cannot drift apart.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shriteq.config import SiteConfig
from shriteq.eval.benchmark import run_benchmark_with_traces

CACHE_DIR = Path("outputs/dashboard")
METRICS_PATH = CACHE_DIR / "metrics.json"
TRACES_PATH = CACHE_DIR / "traces.parquet"
SERIES_PATH = CACHE_DIR / "series.parquet"
META_PATH = CACHE_DIR / "meta.json"

DEPLOYED_MODEL_PATH = "models/ppo_gridedge.zip"

# Only these scalar columns are persisted from each trace row. MPC rows (raw
# ``site.step`` output) and PPO rows (env ``info``) do not share a key set, and
# MPC rows carry a nested ``deferred_energy_kwh`` dict that will not round-trip
# through parquet. Every column below lives in the common ``site.step`` result
# present in *both* traces, so the concatenation is clean and rectangular.
TRACE_COLUMNS = (
    "timestamp",
    "soc",
    "battery_charge_kw",
    "battery_discharge_kw",
    "grid_import_kw",
    "solar_used_kwh",
    "energy_cost",
    "shed_load_kwh",
    "unmet_load_kwh",
)


def _model_mtime(model_path: str | Path) -> float | None:
    path = Path(model_path)
    return path.stat().st_mtime if path.exists() else None


def _trace_frame(rows: list[dict], controller: str) -> pd.DataFrame:
    """Project ``rows`` onto the scalar whitelist and tag the controller."""
    frame = pd.DataFrame([{column: row[column] for column in TRACE_COLUMNS} for row in rows])
    frame["controller"] = controller
    return frame


def build_cache(config: SiteConfig | None = None, seed: int = 42) -> dict:
    """Run the traced benchmark once and persist it under :data:`CACHE_DIR`.

    Returns the same bundle :func:`load_cache` would return, so a caller can use
    the freshly built data without re-reading it from disk.
    """
    config = config or SiteConfig()
    bundle = run_benchmark_with_traces(config, seed)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    METRICS_PATH.write_text(json.dumps(bundle["metrics"], indent=2))

    traces = pd.concat(
        [
            _trace_frame(bundle["traces"]["mpc"], "mpc"),
            _trace_frame(bundle["traces"]["ppo"], "ppo"),
        ],
        ignore_index=True,
    )
    traces.to_parquet(TRACES_PATH, index=False)

    series = pd.DataFrame(
        {
            "load": bundle["load"],
            "solar": bundle["solar"],
        }
    )
    series.index.name = "timestamp"
    series.to_parquet(SERIES_PATH)

    meta = {
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_path": DEPLOYED_MODEL_PATH,
        "model_mtime": _model_mtime(DEPLOYED_MODEL_PATH),
    }
    META_PATH.write_text(json.dumps(meta, indent=2))

    return {
        "metrics": bundle["metrics"],
        "traces": traces,
        "series": series,
        "meta": meta,
    }


def load_cache() -> dict | None:
    """Return the parsed cache bundle, or ``None`` if any file is missing."""
    if not all(path.exists() for path in (METRICS_PATH, TRACES_PATH, SERIES_PATH, META_PATH)):
        return None
    return {
        "metrics": json.loads(METRICS_PATH.read_text()),
        "traces": pd.read_parquet(TRACES_PATH),
        "series": pd.read_parquet(SERIES_PATH),
        "meta": json.loads(META_PATH.read_text()),
    }


def cache_is_stale(meta: dict, model_path: str | Path = DEPLOYED_MODEL_PATH) -> bool:
    """True when the deployed model on disk is newer than the cached run."""
    current = _model_mtime(model_path)
    cached = meta.get("model_mtime")
    if current is None or cached is None:
        return False
    return current > cached
