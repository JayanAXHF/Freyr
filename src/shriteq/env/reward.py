"""Reward calculation for grid dispatch."""

from math import log1p

from shriteq.config import SiteConfig


def compute_reward(
    config: SiteConfig,
    grid_import_kwh: float,
    price: float,
    peak_bump_kva: float,
    demand_rate: float,
    unmet_kwh: float,
    battery_throughput_kwh: float,
    rolling_deferred_kwh: float = 0.0,
    shed_kwh: float = 0.0,
) -> float:
    return (
        -(price * grid_import_kwh)
        - (demand_rate * peak_bump_kva)
        - (config.unmet_penalty * unmet_kwh)
        - (config.cycle_penalty * battery_throughput_kwh)
        - deferred_penalty(config, rolling_deferred_kwh)
        - low_price_shed_penalty(config, price, shed_kwh)
    )


def deferred_penalty(config: SiteConfig, rolling_deferred_kwh: float) -> float:
    """Return a smooth superlinear penalty over the rolling 24-hour shed."""
    amount = max(0.0, rolling_deferred_kwh)
    return config.deferred_cumulative_penalty * amount * log1p(amount)


def low_price_shed_penalty(config: SiteConfig, price: float, shed_kwh: float) -> float:
    """Penalize shedding more when the current tariff is relatively cheap."""
    prices = [float(block["price_inr_per_kwh"]) for block in config.tariff_blocks]
    max_price = max(prices, default=price)
    if max_price <= 0:
        return 0.0
    low_price_factor = max(0.0, min(1.0, 1.0 - float(price) / max_price))
    return config.low_price_shed_penalty * max(0.0, shed_kwh) * low_price_factor
