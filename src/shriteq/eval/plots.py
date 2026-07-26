"""Evaluation plots for dispatch, peaks, costs, and forecasts."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _save(fig, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def plot_daily_dispatch(
    timestamps,
    load,
    solar,
    grid_import,
    battery,
    soc,
    output_path: str | Path = "outputs/daily_dispatch.png",
):
    """Plot load, solar, grid import, battery power, and state of charge."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(timestamps, load, label="Load")
    axes[0].plot(timestamps, solar, label="Solar")
    axes[0].plot(timestamps, grid_import, label="Grid import")
    axes[0].plot(timestamps, battery, label="Battery")
    axes[0].set_ylabel("Power (kW)")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    axes[1].plot(timestamps, soc, color="tab:purple", label="SOC")
    axes[1].set_ylabel("SOC")
    axes[1].set_ylim(0, 1)
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.25)
    return _save(fig, output_path)


def plot_peak_shaving(
    timestamps,
    rolling_peak_kva,
    demand_charge_accumulation,
    output_path: str | Path = "outputs/peak_shaving.png",
):
    """Plot rolling billing peak and accumulated demand charge."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(timestamps, rolling_peak_kva, color="tab:red")
    axes[0].set_ylabel("Rolling peak (kVA)")
    axes[0].grid(alpha=0.25)
    axes[1].plot(timestamps, demand_charge_accumulation, color="tab:orange")
    axes[1].set_ylabel("Demand charge (INR)")
    axes[1].set_xlabel("Time")
    axes[1].grid(alpha=0.25)
    return _save(fig, output_path)


def plot_cost_comparison(
    mpc_metrics: dict,
    ppo_metrics: dict,
    output_path: str | Path = "outputs/cost_comparison.png",
):
    """Compare energy and demand-charge components as stacked bars."""
    labels = ["MPC", "PPO"]
    energy = [mpc_metrics["total_energy_cost"], ppo_metrics["total_energy_cost"]]
    demand = [
        mpc_metrics["demand_charge_incurred"],
        ppo_metrics["demand_charge_incurred"],
    ]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, energy, label="Energy cost")
    ax.bar(labels, demand, bottom=energy, label="Demand charge")
    ax.set_ylabel("Cost (INR)")
    ax.set_title("Cost comparison")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    return _save(fig, output_path)


def plot_forecast_vs_actual(
    timestamps,
    actual_load,
    forecast_load_mean,
    forecast_load_p10,
    forecast_load_p90,
    actual_solar=None,
    forecast_solar_mean=None,
    forecast_solar_p10=None,
    forecast_solar_p90=None,
    output_path: str | Path = "outputs/forecast_vs_actual.png",
):
    """Plot load and optional solar forecasts with uncertainty bands."""
    has_solar = actual_solar is not None and forecast_solar_mean is not None
    fig, axes = plt.subplots(
        2 if has_solar else 1, 1, figsize=(12, 7 if has_solar else 4), sharex=True
    )
    axes = np.atleast_1d(axes)
    axes[0].plot(timestamps, actual_load, label="Actual load", color="black")
    axes[0].plot(
        timestamps, forecast_load_mean, label="Forecast load", color="tab:blue"
    )
    axes[0].fill_between(
        timestamps,
        forecast_load_p10,
        forecast_load_p90,
        alpha=0.2,
        label="Load p10-p90",
    )
    axes[0].set_ylabel("Load (kW)")
    axes[0].legend()
    axes[0].grid(alpha=0.25)
    if has_solar:
        axes[1].plot(timestamps, actual_solar, label="Actual solar", color="black")
        axes[1].plot(
            timestamps, forecast_solar_mean, label="Forecast solar", color="tab:orange"
        )
        if forecast_solar_p10 is not None and forecast_solar_p90 is not None:
            axes[1].fill_between(
                timestamps,
                forecast_solar_p10,
                forecast_solar_p90,
                alpha=0.2,
                label="Solar p10-p90",
            )
        axes[1].set_ylabel("Solar (kW)")
        axes[1].legend()
        axes[1].grid(alpha=0.25)
    axes[-1].set_xlabel("Time")
    return _save(fig, output_path)
