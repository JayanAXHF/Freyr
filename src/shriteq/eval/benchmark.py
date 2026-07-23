"""Comparable MPC and PPO benchmark harness."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame, SiteState
from shriteq.control.mpc import MPCController
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.forecast.tariff import TariffModel
from shriteq.forecast.load_forecaster import LoadForecaster
from shriteq.sim.site_model import SiteModel
from shriteq.sim.load_profiles import generate_load_series


METRICS = (
    "total_energy_cost",
    "demand_charge_incurred",
    "total_bill",
    "peak_kva",
    "unmet_load_kwh",
    "unmet_events",
    "solar_self_consumption",
)


def _scenario(config: SiteConfig, seed: int) -> tuple[pd.Series, pd.Series]:
    source = GridEdgeEnv(config)
    source.reset(seed=seed)
    start = source._position
    end = start + config.episode_days * 96
    return source.load_series.iloc[start:end].copy(), source.solar_series.iloc[start:end].copy()


def _frames(config: SiteConfig, load: pd.Series, solar: pd.Series, position: int) -> list[ForecastFrame]:
    tariff = TariffModel(config)
    frames = []
    end = min(position + 96, len(load))
    for index in range(position, end):
        timestamp = load.index[index]
        tariff_info = tariff.step(timestamp, 0.0)
        frames.append(ForecastFrame(
            timestamp=timestamp,
            load_mean_kw=float(load.iloc[index]),
            load_p10_kw=float(load.iloc[index] * 0.85),
            load_p90_kw=float(load.iloc[index] * 1.15),
            solar_mean_kw=float(solar.iloc[index]),
            solar_p10_kw=float(solar.iloc[index] * 0.9),
            solar_p90_kw=float(solar.iloc[index] * 1.1),
            price_inr_per_kwh=float(tariff_info["tod_price_inr_per_kwh"]),
            demand_rate_inr_per_kva=float(config.demand_charge_inr_per_kva_month),
            tariff_block_id=int(tariff_info["tariff_block_id"]),
        ))
    while len(frames) < 96:
        frames.append(frames[-1])
    return frames


def _metrics(config: SiteConfig, rows: list[dict], solar: pd.Series) -> dict:
    energy_cost = sum(row["energy_cost"] for row in rows)
    peak = max((row["grid_import_kw"] for row in rows), default=0.0)
    solar_total = float(solar.sum() * config.timestep_minutes / 60)
    solar_used = sum(row["solar_used_kwh"] for row in rows)
    demand_charge = peak * config.demand_charge_inr_per_kva_month
    return {
        "total_energy_cost": energy_cost,
        "demand_charge_incurred": demand_charge,
        "total_bill": energy_cost + demand_charge,
        "peak_kva": peak,
        "unmet_load_kwh": sum(row["unmet_load_kwh"] for row in rows),
        "unmet_events": sum(row["unmet_load_kwh"] > 0 for row in rows),
        "solar_self_consumption": solar_used / solar_total if solar_total else 0.0,
    }


def _run_mpc(config: SiteConfig, load: pd.Series, solar: pd.Series, forecast_load: pd.Series | None = None, return_trace: bool = False):
    site = SiteModel(config)
    tariff = TariffModel(config)
    controller = MPCController(config)
    rows = []
    dt_hours = config.timestep_minutes / 60
    RESOLVE_EVERY_N_STEPS = 8  # 2-hour re-solve cadence; see PLAN.md notes on solver cost (~0.38s/solve, 2880 steps/episode)
    plan = None
    for position, timestamp in enumerate(load.index):
        tariff_info = tariff.step(timestamp, 0.0)
        if plan is None or position % RESOLVE_EVERY_N_STEPS == 0:
            state = SiteState(timestamp, site.battery.soc, float(load.iloc[position]), float(solar.iloc[position]), tariff.current_billing_peak_kva, tariff_info["tariff_block_id"], tariff_info["minutes_to_tariff_change"])
            plan = controller.solve(state, _frames(config, forecast_load if forecast_load is not None else load, solar, position))
        assert plan is not None
        charge = max(0.0, -plan.battery_kw)
        discharge = max(0.0, plan.battery_kw)
        result = site.step(float(load.iloc[position]), float(solar.iloc[position]), charge, discharge, plan.hvac_fraction, plan.ev_fraction, plan.pump_fraction)
        tariff_info = tariff.step(timestamp, result["grid_import_kw"])
        rows.append({**result, "timestamp": timestamp, "energy_cost": result["grid_import_kwh"] * tariff_info["tod_price_inr_per_kwh"]})
    metrics = _metrics(config, rows, solar)
    return (metrics, rows) if return_trace else metrics


def _run_ppo(config: SiteConfig, load: pd.Series, solar: pd.Series, return_trace: bool = False):
    env = GridEdgeEnv(config, load_series=load, solar_series=solar)
    observation, _ = env.reset(seed=0)
    model_path = Path("models/ppo_gridedge.zip")
    model = PPO.load(str(model_path), env=env)
    rows = []
    for _ in range(len(load)):
        action, _ = model.predict(observation, deterministic=True)
        observation, _, terminated, _, info = env.step(action)
        rows.append({**info, "timestamp": load.index[len(rows)], "energy_cost": info["grid_import_kwh"] * info["tod_price_inr_per_kwh"], "solar_used_kwh": info["solar_used_kwh"]})
        if terminated:
            break
    metrics = _metrics(config, rows, solar.iloc[:len(rows)])
    return (metrics, rows) if return_trace else metrics


def run_benchmark(config: SiteConfig, seed: int, forecast_driven: bool = False) -> dict:
    """Run MPC and PPO on the same seeded 30-day scenario.

    With ``forecast_driven=True``, the MPC forecast is produced from the
    preceding history only; the oracle mode uses the scenario load directly.
    """
    load, solar = _scenario(config, seed)
    forecast_load = None
    if forecast_driven:
        history = generate_load_series(config, load.index[0] - pd.Timedelta(days=21), 21)
        forecast = LoadForecaster(config).fit(history).predict(len(load))
        forecast_load = pd.Series([frame.load_mean_kw for frame in forecast], index=load.index, name="forecast_load_kw")
    return {"mpc": _run_mpc(config, load, solar, forecast_load), "ppo": _run_ppo(config, load, solar)}


def run_benchmark_with_traces(config: SiteConfig, seed: int) -> dict:
    """Return corrected benchmark metrics together with controller traces."""
    load, solar = _scenario(config, seed)
    mpc_metrics, mpc_trace = _run_mpc(config, load, solar, return_trace=True)
    ppo_metrics, ppo_trace = _run_ppo(config, load, solar, return_trace=True)
    return {
        "metrics": {"mpc": mpc_metrics, "ppo": ppo_metrics},
        "traces": {"mpc": mpc_trace, "ppo": ppo_trace},
        "load": load,
        "solar": solar,
    }
