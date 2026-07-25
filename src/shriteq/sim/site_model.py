"""Core deterministic site simulation."""

from collections import deque

from shriteq.config import SiteConfig
from shriteq.sim.battery import Battery


class SiteModel:
    def __init__(self, config: SiteConfig):
        self.config = config
        self.battery = Battery(config)
        self.deferred_energy_kwh = {"hvac": 0.0, "ev": 0.0, "pump": 0.0}
        self._steps_in_day = 0
        self._shed_history_kwh = deque(maxlen=24 * 60 // config.timestep_minutes)

    def step(
        self,
        load_kw: float,
        solar_kw: float,
        battery_charge_kw: float,
        battery_discharge_kw: float,
        hvac_fraction: float,
        ev_fraction: float,
        pump_fraction: float,
    ) -> dict:
        fractions = [max(0.0, min(1.0, value)) for value in (hvac_fraction, ev_fraction, pump_fraction)]
        flexible_reduction_kw = sum(
            fraction * bound
            for fraction, bound in zip(
                fractions,
                (self.config.hvac_flex_max_kw, self.config.ev_flex_max_kw, self.config.pump_flex_max_kw),
            )
        )
        original_load_kw = max(0.0, load_kw)
        max_shed_kw = original_load_kw * (1.0 - self.config.min_served_load_fraction)
        dt_hours = self.config.timestep_minutes / 60
        remaining_budget_kwh = max(
            0.0,
            self.config.deferred_energy_budget_kwh_per_day
            - sum(self.deferred_energy_kwh.values()),
        )
        actual_shed_kw = min(
            flexible_reduction_kw,
            max_shed_kw,
            remaining_budget_kwh / dt_hours,
        )
        net_load_kw = max(0.0, original_load_kw - actual_shed_kw)
        shed_load_kwh = actual_shed_kw * dt_hours
        self._shed_history_kwh.append(shed_load_kwh)
        rolling_deferred_kwh = sum(self._shed_history_kwh)
        delivered_ratio = actual_shed_kw / flexible_reduction_kw if flexible_reduction_kw else 0.0
        for name, fraction, bound in zip(("hvac", "ev", "pump"), fractions, (self.config.hvac_flex_max_kw, self.config.ev_flex_max_kw, self.config.pump_flex_max_kw)):
            self.deferred_energy_kwh[name] += fraction * bound * delivered_ratio * dt_hours
        charge_kw = min(max(0.0, battery_charge_kw), self.config.max_charge_kw)
        discharge_kw = min(max(0.0, battery_discharge_kw), self.config.max_discharge_kw)
        soc, actual_charge_kw, actual_discharge_kw = self.battery.apply(charge_kw, discharge_kw, self.config.timestep_minutes / 60)
        grid_import_kw = max(0.0, net_load_kw - solar_kw - actual_discharge_kw + actual_charge_kw)
        solar_used_kwh = min(max(0.0, solar_kw), net_load_kw + actual_charge_kw) * dt_hours
        result = {
            "grid_import_kw": grid_import_kw,
            "grid_import_kwh": grid_import_kw * dt_hours,
            "shed_load_kwh": shed_load_kwh,
            # Deferred flexible load is never paid back in this simulator, so the
            # shed energy is a genuine service deficit rather than a free saving.
            "unmet_load_kwh": shed_load_kwh,
            "deferred_load_kwh": shed_load_kwh,
            "deferred_energy_kwh": dict(self.deferred_energy_kwh),
            "rolling_deferred_energy_kwh": rolling_deferred_kwh,
            "served_load_kwh": net_load_kw * self.config.timestep_minutes / 60,
            "solar_used_kwh": solar_used_kwh,
            "curtailed_solar_kwh": max(0.0, solar_kw * dt_hours - solar_used_kwh),
            "soc": soc,
            "battery_charge_kw": actual_charge_kw,
            "battery_discharge_kw": actual_discharge_kw,
            "battery_throughput_kwh": (actual_charge_kw + actual_discharge_kw) * self.config.timestep_minutes / 60,
        }
        self._steps_in_day = (self._steps_in_day + 1) % (24 * 60 // self.config.timestep_minutes)
        if self._steps_in_day == 0:
            self.deferred_energy_kwh = {"hvac": 0.0, "ev": 0.0, "pump": 0.0}
        return result
