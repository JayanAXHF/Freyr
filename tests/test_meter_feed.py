import numpy as np
import pandas as pd
import pytest

from shriteq.config import SiteConfig
from shriteq.sim.load_profiles import generate_load_series
from shriteq.sim.load_source import (
    MIN_HISTORY_STEPS,
    resolve_full_series,
    resolve_history,
    resolve_slice,
    resolve_solar_for,
)
from shriteq.sim.meter_feed import load_meter_series


def _write_series(path, series: pd.Series, *, as_csv: bool):
    frame = pd.DataFrame({"timestamp": series.index, "load_kw": series.to_numpy()})
    if as_csv:
        frame.to_csv(path, index=False)
    else:
        frame.to_parquet(path)


@pytest.mark.parametrize("as_csv", [True, False])
def test_load_meter_series_round_trip(tmp_path, as_csv):
    config = SiteConfig()
    original = generate_load_series(config, "2026-01-01", 5)
    path = tmp_path / ("feed.csv" if as_csv else "feed.parquet")
    _write_series(path, original, as_csv=as_csv)

    loaded = load_meter_series(path, config)

    assert loaded.name == "load_kw"
    assert str(loaded.index.tz) == config.tz
    assert (loaded >= 0).all()
    assert pd.infer_freq(loaded.index) is not None
    np.testing.assert_allclose(loaded.to_numpy(), original.to_numpy(), atol=1e-6)


def test_load_meter_series_resamples_finer_grid(tmp_path):
    config = SiteConfig()
    index = pd.date_range("2026-01-01", periods=20, freq="5min", tz=config.tz)
    series = pd.Series(np.arange(20, dtype=float), index=index)
    path = tmp_path / "feed.csv"
    _write_series(path, series, as_csv=True)

    loaded = load_meter_series(path, config)

    assert pd.infer_freq(loaded.index) == "15min"
    assert len(loaded) == pytest.approx(len(index) / 3, abs=1)


def test_load_meter_series_interpolates_small_gap(tmp_path):
    config = SiteConfig(meter_max_gap_steps=4)
    index = pd.date_range("2026-01-01", periods=20, freq="15min", tz=config.tz)
    values = np.full(20, 5.0)
    series = pd.Series(values, index=index)
    series = series.drop(series.index[5:7])
    path = tmp_path / "feed.csv"
    _write_series(path, series, as_csv=True)

    loaded = load_meter_series(path, config)
    assert not loaded.isna().any()
    assert len(loaded) == 20


def test_load_meter_series_errors_on_large_gap(tmp_path):
    config = SiteConfig(meter_max_gap_steps=2)
    index = pd.date_range("2026-01-01", periods=30, freq="15min", tz=config.tz)
    values = np.full(30, 5.0)
    series = pd.Series(values, index=index)
    series = series.drop(series.index[10:20])
    path = tmp_path / "feed.csv"
    _write_series(path, series, as_csv=True)

    with pytest.raises(ValueError):
        load_meter_series(path, config)


def test_resolvers_fall_through_to_synthetic_when_no_feed():
    config = SiteConfig()
    assert config.meter_feed_path is None

    assert resolve_full_series(config).equals(
        generate_load_series(config, "2026-01-01", 90)
    )

    before = pd.Timestamp("2026-03-01")
    assert resolve_history(config, before, 21).equals(
        generate_load_series(config, before - pd.Timedelta(days=21), 21)
    )

    assert resolve_slice(config, "2026-06-01", 30, edge="tail").equals(
        generate_load_series(config, "2026-06-01", 30)
    )
    assert resolve_slice(config, "2026-01-05", 14, edge="head").equals(
        generate_load_series(config, "2026-01-05", 14)
    )

    load = generate_load_series(config, "2026-01-05", 14)
    from shriteq.forecast.solar_synth import generate as generate_solar

    assert resolve_solar_for(config, load, "2026-01-05", 14).equals(
        generate_solar(config, "2026-01-05", 14)
    )


def test_resolve_history_clamps_near_feed_start(tmp_path):
    config = SiteConfig()
    full = generate_load_series(config, "2026-01-01", 60)
    path = tmp_path / "feed.parquet"
    _write_series(path, full, as_csv=False)
    config = SiteConfig(meter_feed_path=str(path))

    before_ts = full.index[MIN_HISTORY_STEPS + 5]
    history = resolve_history(config, before_ts, 21)
    assert (history.index < before_ts).all()
    assert len(history) <= 21 * (24 * 60 // config.timestep_minutes)
    assert len(history) >= MIN_HISTORY_STEPS


def test_resolve_history_errors_when_insufficient(tmp_path):
    config = SiteConfig()
    full = generate_load_series(config, "2026-01-01", 60)
    path = tmp_path / "feed.parquet"
    _write_series(path, full, as_csv=False)
    config = SiteConfig(meter_feed_path=str(path))

    before_ts = full.index[1]
    with pytest.raises(ValueError):
        resolve_history(config, before_ts, 21)


def test_end_to_end_on_feed(tmp_path):
    from shriteq.env.grid_edge_env import GridEdgeEnv
    from shriteq.eval.benchmark import run_benchmark
    from shriteq.sim.load_source import FORECAST_HISTORY_DAYS

    config = SiteConfig()
    full = generate_load_series(config, "2026-01-01", 60)
    path = tmp_path / "feed.parquet"
    _write_series(path, full, as_csv=False)
    config = SiteConfig(meter_feed_path=str(path), episode_days=5)

    env = GridEdgeEnv(config)
    reserve = FORECAST_HISTORY_DAYS * (24 * 60 // config.timestep_minutes)
    assert env.load_series.equals(full.iloc[reserve:])
    assert len(env.solar_series) == len(env.load_series)
    assert (env.load_series.index == env.solar_series.index).all()

    metrics = run_benchmark(config, seed=0, model_path="models/ppo_gridedge.zip")
    assert metrics["mpc"]["total_bill"] >= 0
