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
