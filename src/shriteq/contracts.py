"""Data contracts shared by forecasting, state, and dispatch components."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ForecastFrame:
    timestamp: datetime
    load_mean_kw: float
    load_p10_kw: float
    load_p90_kw: float
    solar_mean_kw: float
    solar_p10_kw: float
    solar_p90_kw: float
    price_inr_per_kwh: float
    demand_rate_inr_per_kva: float
    tariff_block_id: int


@dataclass
class SiteState:
    timestamp: datetime
    soc: float
    current_load_kw: float
    current_solar_kw: float
    current_billing_peak_kva: float
    current_tariff_block: int
    minutes_to_tariff_change: int
    remaining_shed_budget_kwh: float = 0.0


@dataclass
class DispatchPlan:
    step: int
    battery_kw: float
    hvac_fraction: float
    ev_fraction: float
    pump_fraction: float
    grid_import_kw: float
    predicted_peak_kva: float
