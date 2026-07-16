"""Core deterministic site simulation."""

from shriteq.config import SiteConfig
from shriteq.sim.battery import Battery


class SiteModel:
    def __init__(self, config: SiteConfig):
        self.config = config
        self.battery = Battery(config)

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
        net_load_kw = max(0.0, load_kw - flexible_reduction_kw)
        charge_kw = min(max(0.0, battery_charge_kw), self.config.max_charge_kw)
        discharge_kw = min(max(0.0, battery_discharge_kw), self.config.max_discharge_kw)
        self.battery.apply(charge_kw, discharge_kw, self.config.timestep_minutes / 60)
        grid_import_kw = max(0.0, net_load_kw - solar_kw - discharge_kw + charge_kw)
        unmet_load_kwh = max(0.0, (net_load_kw - solar_kw - discharge_kw) * self.config.timestep_minutes / 60)
        return {
            "grid_import_kw": grid_import_kw,
            "grid_import_kwh": grid_import_kw * self.config.timestep_minutes / 60,
            "unmet_load_kwh": unmet_load_kwh,
            "soc": self.battery.soc,
            "battery_throughput_kwh": (charge_kw + discharge_kw) * self.config.timestep_minutes / 60,
        }
