"""Convex model-predictive controller for site dispatch."""

from __future__ import annotations

import cvxpy as cp
import numpy as np

from shriteq.config import SiteConfig
from shriteq.contracts import DispatchPlan, ForecastFrame, SiteState


class MPCController:
    horizon = 96

    def __init__(self, config: SiteConfig):
        self.config = config
        self.problem: cp.Problem | None = None

    def solve(self, site_state: SiteState, forecast_frames: list[ForecastFrame]) -> DispatchPlan:
        if len(forecast_frames) != self.horizon:
            raise ValueError(f"MPC requires exactly {self.horizon} forecast frames")

        config = self.config
        load = np.array([frame.load_mean_kw for frame in forecast_frames], dtype=float)
        solar = np.array([frame.solar_mean_kw for frame in forecast_frames], dtype=float)
        prices = np.array([frame.price_inr_per_kwh for frame in forecast_frames], dtype=float)
        demand_rates = np.array([frame.demand_rate_inr_per_kva for frame in forecast_frames], dtype=float)
        dt_hours = config.timestep_minutes / 60.0

        grid_import = cp.Variable(self.horizon, nonneg=True)
        battery_charge = cp.Variable(self.horizon, nonneg=True)
        battery_discharge = cp.Variable(self.horizon, nonneg=True)
        soc = cp.Variable(self.horizon)
        hvac = cp.Variable(self.horizon)
        ev = cp.Variable(self.horizon)
        pump = cp.Variable(self.horizon)
        curtailment = cp.Variable(self.horizon, nonneg=True)
        peak_kva = cp.Variable(self.horizon, nonneg=True)
        unmet = cp.Variable(self.horizon, nonneg=True)

        constraints = [
            battery_charge <= config.max_charge_kw,
            battery_discharge <= config.max_discharge_kw,
            soc >= config.soc_min,
            soc <= config.soc_max,
            hvac >= 0,
            hvac <= 1,
            ev >= 0,
            ev <= 1,
            pump >= 0,
            pump <= 1,
            curtailment <= solar,
            peak_kva >= grid_import,
        ]
        effective_load = load - (
            config.hvac_flex_max_kw * hvac
            + config.ev_flex_max_kw * ev
            + config.pump_flex_max_kw * pump
        )
        constraints.append(
            grid_import + battery_discharge + unmet
            == effective_load - solar + curtailment + battery_charge
        )
        constraints.append(
            soc[0]
            == site_state.soc
            + (battery_charge[0] * config.round_trip_efficiency**0.5 - battery_discharge[0] / config.round_trip_efficiency**0.5)
            * dt_hours / config.battery_capacity_kwh
        )
        for index in range(1, self.horizon):
            constraints.append(
                soc[index]
                == soc[index - 1]
                + (battery_charge[index] * config.round_trip_efficiency**0.5 - battery_discharge[index] / config.round_trip_efficiency**0.5)
                * dt_hours / config.battery_capacity_kwh
            )

        objective = cp.Minimize(
            cp.sum(cp.multiply(prices, grid_import)) * dt_hours
            + demand_rates[-1] * peak_kva[-1]
            + config.wear_cost * cp.sum(battery_charge + battery_discharge) * dt_hours
            + config.unmet_penalty * cp.sum(unmet) * dt_hours
        )
        self.problem = cp.Problem(objective, constraints)
        try:
            self.problem.solve(solver=cp.OSQP)
        except Exception:
            self.problem.solve(solver=cp.ECOS)
        if self.problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(f"MPC solve failed with status {self.problem.status}")

        return DispatchPlan(
            step=0,
            battery_kw=float(battery_discharge.value[0] - battery_charge.value[0]),
            hvac_fraction=float(hvac.value[0]),
            ev_fraction=float(ev.value[0]),
            pump_fraction=float(pump.value[0]),
            grid_import_kw=float(grid_import.value[0]),
            predicted_peak_kva=float(peak_kva.value[0]),
        )
