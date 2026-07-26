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
        - shed_energy_penalty(price, shed_kwh)
    )


def deferred_penalty(config: SiteConfig, rolling_deferred_kwh: float) -> float:
    """Return a smooth superlinear penalty over the rolling 24-hour shed."""
    amount = max(0.0, rolling_deferred_kwh)
    return config.deferred_cumulative_penalty * amount * log1p(amount)


def peak_potential(config: SiteConfig, grid_import_kw: float) -> float:
    """Potential ``Phi(s)`` for optional potential-based reward shaping.

    Returns 0 unless ``reward_shaping_enabled``. The env adds the shaping term
    ``Phi(s') - Phi(s)`` to the reward; being a potential difference it is
    provably policy-invariant, so the reported bill is unchanged. It only gives
    a denser gradient toward keeping grid import below a soft target.
    """
    if not config.reward_shaping_enabled:
        return 0.0
    excess = max(0.0, float(grid_import_kw) - config.reward_shaping_soft_target_kw)
    return -config.reward_shaping_coef * excess


def shed_energy_penalty(price: float, shed_kwh: float) -> float:
    """Charge shed flexible load its avoided-energy value.

    Shedding lowers grid import, so without this term deferring load is a free
    way to dodge both energy cost and demand charges -- the policy learns to
    shed all the way to the daily budget cap.  Charging ``price * shed_kwh``
    cancels that windfall, and unlike the old ``low_price_shed_penalty`` the
    charge is *largest at peak price* (exactly when shedding used to be free).
    The comfort cost of the deferral is charged separately through the
    ``unmet_penalty * unmet_kwh`` term -- ``site_model`` now records shed load
    as unmet in this no-payback simulator, mirroring the MPC objective's
    ``unmet_penalty * flex_reduction`` charge.
    """
    return max(0.0, float(price)) * max(0.0, float(shed_kwh))
