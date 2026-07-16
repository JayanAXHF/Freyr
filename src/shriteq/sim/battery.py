"""Simple bounded battery model."""

from __future__ import annotations

from shriteq.config import SiteConfig


class Battery:
    def __init__(self, config: SiteConfig, initial_soc: float | None = None):
        self.config = config
        self.soc = config.soc_min if initial_soc is None else self._bounded(initial_soc)

    def _bounded(self, soc: float) -> float:
        return min(self.config.soc_max, max(self.config.soc_min, soc))

    def apply(self, charge_kw: float, discharge_kw: float, dt_hours: float) -> float:
        charge_kw = min(max(0.0, charge_kw), self.config.max_charge_kw)
        discharge_kw = min(max(0.0, discharge_kw), self.config.max_discharge_kw)
        one_way_efficiency = self.config.round_trip_efficiency**0.5
        self.soc = self._bounded(
            self.soc
            + charge_kw * dt_hours * one_way_efficiency / self.config.battery_capacity_kwh
            - discharge_kw * dt_hours / one_way_efficiency / self.config.battery_capacity_kwh
        )
        return self.soc
