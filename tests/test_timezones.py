import pytest

from shriteq.config import SiteConfig
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.forecast.solar_synth import generate as generate_solar
from shriteq.sim.load_profiles import generate_load_series


def test_load_and_solar_use_the_same_timezone():
    config = SiteConfig()
    load = generate_load_series(config, "2026-01-05", 1)
    solar = generate_solar(config, "2026-01-05", 1)
    assert load.index.tz == solar.index.tz
    assert str(load.index.tz) == config.tz
    GridEdgeEnv(config, load_series=load, solar_series=solar)


def test_environment_rejects_mismatched_timezones():
    config = SiteConfig()
    load = generate_load_series(config, "2026-01-05", 1).tz_localize(None)
    solar = generate_solar(config, "2026-01-05", 1)
    with pytest.raises(ValueError, match="same timezone"):
        GridEdgeEnv(config, load_series=load, solar_series=solar)


def test_observation_does_not_mutate_tariff_state():
    config = SiteConfig()
    load = generate_load_series(config, "2026-01-05", 2)
    solar = generate_solar(config, "2026-01-05", 2)
    env = GridEdgeEnv(config, load_series=load, solar_series=solar)
    env.reset(seed=1)
    env.tariff.current_billing_peak_kva = 12.0
    cycle_start = env.tariff._cycle_start
    env._observation()
    env._observation()
    assert env.tariff.current_billing_peak_kva == 12.0
    assert env.tariff._cycle_start == cycle_start
