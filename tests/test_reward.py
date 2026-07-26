from shriteq.config import SiteConfig
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.env.reward import compute_reward
from shriteq.forecast.solar_synth import generate as generate_solar
from shriteq.sim.load_profiles import generate_load_series
import pytest


def test_new_peak_is_penalized():
    no_peak = compute_reward(SiteConfig(), 1, 8, 0, 250, 0, 0)
    new_peak = compute_reward(SiteConfig(), 1, 8, 1, 250, 0, 0)
    assert new_peak < no_peak


@pytest.mark.parametrize("unmet_penalty", [100.0, 1000.0])
def test_reward_uses_caller_config(unmet_penalty):
    config = SiteConfig(unmet_penalty=unmet_penalty)
    reward = compute_reward(config, 0, 0, 0, 0, 1, 0)
    assert reward == -unmet_penalty


def test_deferred_penalty_is_nonnegative_and_monotonic():
    from shriteq.env.reward import deferred_penalty

    config = SiteConfig()
    assert deferred_penalty(config, 0.0) == 0.0
    assert deferred_penalty(config, 20.0) > deferred_penalty(config, 1.25)


def test_shed_energy_penalty_scales_up_with_price():
    from shriteq.env.reward import shed_energy_penalty

    cheap = shed_energy_penalty(5.0, 1.0)
    peak = shed_energy_penalty(10.0, 1.0)
    # Shedding must cost its avoided-energy value, so it is penalized *more*
    # at peak price -- the opposite of the old (backwards) low-price term.
    assert peak > cheap > 0.0
    assert shed_energy_penalty(10.0, 0.0) == 0.0


def test_environment_reward_matches_info_arithmetic():
    config = SiteConfig(episode_days=1)
    load = generate_load_series(config, "2026-01-05", 2)
    solar = generate_solar(config, "2026-01-05", 2)
    env = GridEdgeEnv(config, load_series=load, solar_series=solar)
    env.reset(seed=0)
    _, reward, _, _, info = env.step([0.0, 1.0, 1.0, 1.0])
    expected = compute_reward(
        config,
        info["grid_import_kwh"],
        info["tod_price_inr_per_kwh"],
        info["peak_bump_kva"],
        config.demand_charge_inr_per_kva_month,
        info["unmet_load_kwh"],
        info["battery_throughput_kwh"],
        info["rolling_deferred_energy_kwh"],
        info["shed_load_kwh"],
    )
    assert info["shed_load_kwh"] > 0.0
    # Shed flexible load is now recorded as unmet service (no payback modelled).
    assert info["unmet_load_kwh"] == info["shed_load_kwh"]
    assert reward == expected
