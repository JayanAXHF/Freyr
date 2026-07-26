"""Simple bounded battery model."""

from __future__ import annotations

from shriteq.config import SiteConfig


class Battery:
    def __init__(self, config: SiteConfig, initial_soc: float | None = None):
        self.config = config
        self.soc = (
            ((config.soc_min + config.soc_max) / 2)
            if initial_soc is None
            else self._bounded(initial_soc)
        )

    def _bounded(self, soc: float) -> float:
        return min(self.config.soc_max, max(self.config.soc_min, soc))

    def apply(
        self, charge_kw: float, discharge_kw: float, dt_hours: float
    ) -> tuple[float, float, float]:
        if dt_hours <= 0:
            raise ValueError("dt_hours must be positive")
        requested_charge_kw = min(max(0.0, charge_kw), self.config.max_charge_kw)
        requested_discharge_kw = min(
            max(0.0, discharge_kw), self.config.max_discharge_kw
        )
        one_way_efficiency = self.config.round_trip_efficiency**0.5
        available_storage_kwh = max(
            0.0, (self.config.soc_max - self.soc) * self.config.battery_capacity_kwh
        )
        available_energy_kwh = max(
            0.0, (self.soc - self.config.soc_min) * self.config.battery_capacity_kwh
        )
        actual_charge_kw = min(
            requested_charge_kw, available_storage_kwh / (dt_hours * one_way_efficiency)
        )
        actual_discharge_kw = min(
            requested_discharge_kw, available_energy_kwh * one_way_efficiency / dt_hours
        )
        self.soc = self._bounded(
            self.soc
            + actual_charge_kw
            * dt_hours
            * one_way_efficiency
            / self.config.battery_capacity_kwh
            - actual_discharge_kw
            * dt_hours
            / one_way_efficiency
            / self.config.battery_capacity_kwh
        )
        return self.soc, actual_charge_kw, actual_discharge_kw
