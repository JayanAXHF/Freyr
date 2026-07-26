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

    def solve(
        self, site_state: SiteState, forecast_frames: list[ForecastFrame]
    ) -> DispatchPlan:
        if len(forecast_frames) != self.horizon:
            raise ValueError(f"MPC requires exactly {self.horizon} forecast frames")

        config = self.config
        load = np.array([frame.load_mean_kw for frame in forecast_frames], dtype=float)
        solar = np.array(
            [frame.solar_mean_kw for frame in forecast_frames], dtype=float
        )
        prices = np.array(
            [frame.price_inr_per_kwh for frame in forecast_frames], dtype=float
        )
        demand_rates = np.array(
            [frame.demand_rate_inr_per_kva for frame in forecast_frames], dtype=float
        )
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
        self._flex_variables = (hvac, ev, pump)

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
        # The billed peak is the maximum import over the horizon.  Because
        # the objective uses peak_kva[-1], make peak_kva a running maximum so
        # earlier spikes cannot escape the demand-charge term.
        constraints.append(peak_kva[0] >= site_state.current_billing_peak_kva)
        for index in range(1, self.horizon):
            constraints.append(peak_kva[index] >= peak_kva[index - 1])
        effective_load = load - (
            config.hvac_flex_max_kw * hvac
            + config.ev_flex_max_kw * ev
            + config.pump_flex_max_kw * pump
        )
        flex_reduction = load - effective_load
        constraints.append(
            flex_reduction <= load * (1.0 - config.min_served_load_fraction)
        )
        steps_per_day = 24 * 60 // config.timestep_minutes
        step_in_day = (
            site_state.timestamp.hour * 60 + site_state.timestamp.minute
        ) // config.timestep_minutes
        steps_left_in_day = max(1, steps_per_day - step_in_day)
        constraints.append(
            cp.sum(flex_reduction[:steps_left_in_day]) * dt_hours
            <= site_state.remaining_shed_budget_kwh
        )
        low_price_factor = np.maximum(
            0.0, 1.0 - prices / max(float(np.max(prices)), 1e-9)
        )
        remaining_flex = flex_reduction[:steps_left_in_day] * dt_hours
        cumulative_flex = cp.cumsum(remaining_flex)
        constraints.append(
            grid_import + battery_discharge + unmet
            == effective_load - solar + curtailment + battery_charge
        )
        constraints.append(
            soc[0]
            == site_state.soc
            + (
                battery_charge[0] * config.round_trip_efficiency**0.5
                - battery_discharge[0] / config.round_trip_efficiency**0.5
            )
            * dt_hours
            / config.battery_capacity_kwh
        )
        for index in range(1, self.horizon):
            constraints.append(
                soc[index]
                == soc[index - 1]
                + (
                    battery_charge[index] * config.round_trip_efficiency**0.5
                    - battery_discharge[index] / config.round_trip_efficiency**0.5
                )
                * dt_hours
                / config.battery_capacity_kwh
            )

        objective = cp.Minimize(
            cp.sum(cp.multiply(prices, grid_import)) * dt_hours
            + demand_rates[-1] * peak_kva[-1]
            + config.wear_cost * cp.sum(battery_charge + battery_discharge) * dt_hours
            + config.unmet_penalty * (cp.sum(unmet) + cp.sum(flex_reduction)) * dt_hours
            + cp.sum(
                cp.multiply(
                    config.low_price_shed_penalty * low_price_factor,
                    flex_reduction,
                )
            )
            * dt_hours
            + config.deferred_cumulative_penalty * cp.sum_squares(cumulative_flex)
        )
        self.problem = cp.Problem(objective, constraints)
        try:
            self.problem.solve(solver=cp.OSQP)
        except Exception:
            self.problem.solve(solver=cp.ECOS)
        # Do not accept OSQP's ``optimal_inaccurate`` result as final.  In
        # this model it can contain a materially infeasible dispatch even
        # though CVXPY exposes variable values.  Re-solve with the more
        # conservative fallback solver and only then accept an inaccurate
        # status if that is the best available result.
        if self.problem.status != cp.OPTIMAL:
            self.problem.solve(solver=cp.ECOS)
        if self.problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
            raise RuntimeError(
                f"MPC solve failed after OSQP/ECOS with status {self.problem.status}"
            )

        return DispatchPlan(
            step=0,
            battery_kw=float(battery_discharge.value[0] - battery_charge.value[0]),
            hvac_fraction=float(np.clip(hvac.value[0], 0.0, 1.0)),
            ev_fraction=float(np.clip(ev.value[0], 0.0, 1.0)),
            pump_fraction=float(np.clip(pump.value[0], 0.0, 1.0)),
            grid_import_kw=float(max(0.0, grid_import.value[0])),
            predicted_peak_kva=float(max(0.0, peak_kva.value[0])),
        )

    def flex_fractions_at(self, step: int) -> tuple[float, float, float]:
        """Return the solved horizon flex decisions at ``step``."""
        if self.problem is None or not 0 <= step < self.horizon:
            raise ValueError("step is outside the solved MPC horizon")
        return tuple(
            float(np.clip(variable.value[step], 0.0, 1.0))
            for variable in self._flex_variables
        )
