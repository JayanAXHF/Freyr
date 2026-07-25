"""Shared dashboard-payload builder for the Streamlit page, the TUI server, and
the static snapshot exporter.

One expensive call to ``run_benchmark_with_traces`` produces the MPC+learned
metrics *and* the per-step traces in a single pass; everything else (the "Now"
tiles and the next-24h forecast) is cheap. The returned dict is the wire format
consumed by ``tui_viewer`` (see ``src/tui_viewer/src/data/model.rs``).
"""

from __future__ import annotations

import math

import numpy as np

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame, SiteState
from shriteq.control.mpc import MPCController
from shriteq.eval.benchmark import METRICS, run_benchmark_with_traces
from shriteq.forecast.solar_synth import generate as generate_solar
from shriteq.forecast.tariff import TariffModel
from shriteq.sim.load_profiles import generate_load_series

# Target number of points to keep in the animated-playback trace. The raw trace
# is one 30-day episode (~2880 steps); downsampling keeps the JSON small and the
# animation smooth on a 3.5" kiosk.
TRACE_TARGET_POINTS = 250


def _now_and_forecast(config: SiteConfig) -> tuple[dict, list[dict]]:
    """Reproduce the Streamlit "Now" tiles and next-24h chart inputs."""
    load = generate_load_series(config, "2026-01-05", 14)
    solar = generate_solar(config, "2026-01-05", 14)
    frames = [
        ForecastFrame(
            timestamp=load.index[i],
            load_mean_kw=float(load.iloc[i]),
            load_p10_kw=float(load.iloc[i] * 0.9),
            load_p90_kw=float(load.iloc[i] * 1.1),
            solar_mean_kw=float(solar.iloc[i]),
            solar_p10_kw=float(solar.iloc[i] * 0.9),
            solar_p90_kw=float(solar.iloc[i] * 1.1),
            price_inr_per_kwh=8.0,
            demand_rate_inr_per_kva=float(config.demand_charge_inr_per_kva_month),
            tariff_block_id=0,
        )
        for i in range(96)
    ]
    tariff = TariffModel(config)
    tariff_info = tariff.step(load.index[0], 0.0)
    site_state = SiteState(
        load.index[0],
        0.5,
        float(load.iloc[0]),
        float(solar.iloc[0]),
        tariff_info["current_billing_peak_kva"],
        tariff_info["tariff_block_id"],
        tariff_info["minutes_to_tariff_change"],
    )
    plan = MPCController(config).solve(site_state, frames)

    now = {
        "load_kw": float(load.iloc[0]),
        "solar_kw": float(solar.iloc[0]),
        "soc": float(site_state.soc),
        "tariff_block": int(site_state.current_tariff_block),
        "billing_peak_kva": float(site_state.current_billing_peak_kva),
    }
    forecast = [
        {
            "t": load.index[i].isoformat(),
            "load_kw": float(load.iloc[i]),
            "solar_kw": float(solar.iloc[i]),
            "grid_import_kw": float(plan.grid_import_kw),
        }
        for i in range(96)
    ]
    return now, forecast


def _benchmark_rows(metrics: dict) -> dict:
    """Turn the raw MPC/PPO metric dicts into wire rows with savings + quality
    flags, exactly as ``dashboard.py`` computes them."""
    mpc = metrics["mpc"]
    mpc_shed = mpc["shed_load_kwh"]
    mpc_events = mpc["shed_events"]
    mpc_bill = mpc["total_bill"]

    def row(source: dict) -> dict:
        service_quality_ok = bool(
            source["shed_load_kwh"] <= mpc_shed * 1.5
            and source["shed_events"] <= mpc_events * 1.5
        )
        savings_pct = (
            (1.0 - source["total_bill"] / mpc_bill) * 100.0
            if service_quality_ok and mpc_bill
            else None
        )
        out = {metric: float(source[metric]) for metric in METRICS}
        out["service_quality_ok"] = service_quality_ok
        out["savings_pct"] = savings_pct
        return out

    return {"mpc": row(mpc), "learned": row(metrics["ppo"])}


def _downsample_trace(mpc_rows: list[dict], ppo_rows: list[dict]) -> dict:
    """Build the animated-playback trace, downsampled to ~TRACE_TARGET_POINTS."""
    n = len(ppo_rows)
    if n == 0:
        return {
            "timestamps": [],
            "learned": {"grid_import_kw": [], "soc": []},
            "mpc": {"grid_import_kw": []},
            "rolling_peak_learned": [],
        }
    learned_import = np.array([float(r["grid_import_kw"]) for r in ppo_rows])
    rolling_peak = np.maximum.accumulate(learned_import)
    step = max(1, math.ceil(n / TRACE_TARGET_POINTS))
    idx = list(range(0, n, step))

    def at(rows: list[dict], key: str, i: int) -> float:
        return float(rows[i][key]) if i < len(rows) else 0.0

    return {
        "timestamps": [ppo_rows[i]["timestamp"].isoformat() for i in idx],
        "learned": {
            "grid_import_kw": [float(learned_import[i]) for i in idx],
            "soc": [at(ppo_rows, "soc", i) for i in idx],
        },
        "mpc": {"grid_import_kw": [at(mpc_rows, "grid_import_kw", i) for i in idx]},
        "rolling_peak_learned": [float(rolling_peak[i]) for i in idx],
    }


def build_dashboard_payload(config: SiteConfig | None = None, seed: int = 42) -> dict:
    """Build the full dashboard payload (now + forecast + benchmark + trace)."""
    config = config or SiteConfig()
    now, forecast = _now_and_forecast(config)
    result = run_benchmark_with_traces(config, seed)
    benchmark = _benchmark_rows(result["metrics"])
    trace = _downsample_trace(result["traces"]["mpc"], result["traces"]["ppo"])
    return {
        "seed": seed,
        "now": now,
        "forecast": forecast,
        "benchmark": benchmark,
        "trace": trace,
    }
