"""Unit tests for the dashboard cache contract.

These do not need a trained PPO model: ``run_benchmark_with_traces`` is
monkeypatched with a bundle shaped exactly like the real one (MPC rows carry a
nested ``deferred_energy_kwh`` dict; PPO rows carry extra tariff keys), so the
tests exercise the whitelist projection, the parquet round-trip, and the
staleness check in isolation.
"""

from __future__ import annotations

import pandas as pd
import pytest

from shriteq.config import SiteConfig
from shriteq.eval import dashboard_cache as dc


def _mpc_row(ts):
    # Shape of a raw SiteModel.step result + timestamp + energy_cost.
    return {
        "grid_import_kw": 5.0, "grid_import_kwh": 1.25, "shed_load_kwh": 0.0,
        "unmet_load_kwh": 0.0, "deferred_load_kwh": 0.0,
        "deferred_energy_kwh": {"hvac": 0.1, "ev": 0.0, "pump": 0.0},  # nested dict
        "rolling_deferred_energy_kwh": 0.0, "served_load_kwh": 1.0,
        "solar_used_kwh": 0.5, "curtailed_solar_kwh": 0.0, "soc": 0.5,
        "battery_charge_kw": 2.0, "battery_discharge_kw": 0.0,
        "battery_throughput_kwh": 0.5, "timestamp": ts, "energy_cost": 8.0,
    }


def _ppo_row(ts):
    # Env info: MPC-style result plus tariff fields and extras.
    row = _mpc_row(ts)
    row.update({
        "tod_price_inr_per_kwh": 8.0, "tariff_block_id": 1, "peak_bump_kva": 0.0,
        "current_billing_peak_kva": 10.0, "bill_delta_inr": 8.0, "deferred_penalty": 0.0,
    })
    return row


def _bundle(n=96):
    idx = pd.date_range("2026-01-05", periods=n, freq="15min", tz="Asia/Kolkata")
    metrics = {"total_bill": 1.0, "total_energy_cost": 1.0, "demand_charge_incurred": 1.0}
    return {
        "metrics": {"mpc": {**metrics, "total_bill": 100.0}, "ppo": {**metrics, "total_bill": 84.0}},
        "traces": {"mpc": [_mpc_row(t) for t in idx], "ppo": [_ppo_row(t) for t in idx]},
        "load": pd.Series(range(n), index=idx, dtype=float, name="load"),
        "solar": pd.Series(range(n), index=idx, dtype=float, name="solar"),
    }


@pytest.fixture
def cache_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(dc, "METRICS_PATH", tmp_path / "metrics.json")
    monkeypatch.setattr(dc, "TRACES_PATH", tmp_path / "traces.parquet")
    monkeypatch.setattr(dc, "SERIES_PATH", tmp_path / "series.parquet")
    monkeypatch.setattr(dc, "META_PATH", tmp_path / "meta.json")
    monkeypatch.setattr(dc, "run_benchmark_with_traces", lambda config, seed: _bundle())
    return tmp_path


def test_load_cache_none_when_missing(cache_in_tmp):
    assert dc.load_cache() is None


def test_build_then_load_round_trip(cache_in_tmp):
    dc.build_cache(SiteConfig(), seed=42)
    loaded = dc.load_cache()
    assert loaded is not None

    traces = loaded["traces"]
    # Whitelist only: the nested dict and tariff-only columns are dropped, and
    # both controllers land in one rectangular frame with a controller tag.
    assert set(traces.columns) == set(dc.TRACE_COLUMNS) | {"controller"}
    assert set(traces["controller"].unique()) == {"mpc", "ppo"}
    assert "deferred_energy_kwh" not in traces.columns
    assert not any(str(traces[c].dtype) == "object" for c in dc.TRACE_COLUMNS)

    assert list(loaded["series"].columns) == ["load", "solar"]
    assert loaded["metrics"]["mpc"]["total_bill"] == 100.0
    assert loaded["metrics"]["ppo"]["total_bill"] == 84.0
    assert loaded["meta"]["seed"] == 42


def test_cache_is_stale_rules(tmp_path):
    model = tmp_path / "model.zip"
    model.write_text("x")
    mtime = model.stat().st_mtime
    # Model unchanged since the cache was built -> not stale.
    assert dc.cache_is_stale({"model_mtime": mtime}, model_path=model) is False
    # Model newer than the cache -> stale.
    assert dc.cache_is_stale({"model_mtime": mtime - 100}, model_path=model) is True
    # Missing model or missing cached mtime -> never flagged.
    assert dc.cache_is_stale({"model_mtime": None}, model_path=model) is False
    assert dc.cache_is_stale({"model_mtime": mtime}, model_path=tmp_path / "absent.zip") is False
