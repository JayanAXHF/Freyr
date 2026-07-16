"""Reward calculation for grid dispatch."""

from shriteq.config import SiteConfig


def compute_reward(
    grid_import_kwh: float,
    price: float,
    peak_bump_kva: float,
    demand_rate: float,
    unmet_kwh: float,
    battery_throughput_kwh: float,
) -> float:
    config = SiteConfig()
    return (
        -(price * grid_import_kwh)
        - (demand_rate * peak_bump_kva)
        - (config.unmet_penalty * unmet_kwh)
        - (config.cycle_penalty * battery_throughput_kwh)
    )
