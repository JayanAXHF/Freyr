"""Configuration for a site energy-management episode."""

from dataclasses import dataclass, field


@dataclass
class SiteConfig:
    """Static site parameters and operating bounds."""

    battery_capacity_kwh: float = 100.0
    max_charge_kw: float = 25.0
    max_discharge_kw: float = 25.0
    round_trip_efficiency: float = 0.9
    soc_min: float = 0.1
    soc_max: float = 0.9

    hvac_flex_min_kw: float = 0.0
    hvac_flex_max_kw: float = 20.0
    ev_flex_min_kw: float = 0.0
    ev_flex_max_kw: float = 15.0
    pump_flex_min_kw: float = 0.0
    pump_flex_max_kw: float = 10.0

    tariff_blocks: list[dict[str, float]] = field(
        default_factory=lambda: [
            {"start_hour": 0, "end_hour": 6, "price_inr_per_kwh": 5.0},
            {"start_hour": 6, "end_hour": 18, "price_inr_per_kwh": 8.0},
            {"start_hour": 18, "end_hour": 22, "price_inr_per_kwh": 10.0},
            {"start_hour": 22, "end_hour": 24, "price_inr_per_kwh": 6.0},
        ]
    )
    demand_charge_inr_per_kva_month: float = 250.0

    lat: float = 28.4
    lon: float = 77.1
    tz: str = "Asia/Kolkata"
    timestep_minutes: int = 15
    episode_days: int = 30
    unmet_penalty: float = 500.0
    cycle_penalty: float = 0.1
    wear_cost: float = 0.05
    min_served_load_fraction: float = 0.5
    deferred_energy_budget_kwh_per_day: float = 24.0
    deferred_cumulative_penalty: float = 1.0
