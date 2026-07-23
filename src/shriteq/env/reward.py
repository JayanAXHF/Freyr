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
) -> float:
    return (
        -(price * grid_import_kwh)
        - (demand_rate * peak_bump_kva)
        - (config.unmet_penalty * unmet_kwh)
        - (config.cycle_penalty * battery_throughput_kwh)
        - deferred_penalty(config, rolling_deferred_kwh)
    )


def deferred_penalty(config: SiteConfig, rolling_deferred_kwh: float) -> float:
    """Return a smooth superlinear penalty over the rolling 24-hour shed."""
    amount = max(0.0, rolling_deferred_kwh)
    return config.deferred_cumulative_penalty * amount * log1p(amount)
