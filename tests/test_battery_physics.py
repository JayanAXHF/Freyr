from shriteq.config import SiteConfig
from shriteq.sim.battery import Battery
from shriteq.sim.site_model import SiteModel


def test_near_empty_battery_returns_actual_discharge_and_grid_shortfall():
    config = SiteConfig(soc_min=0.1, soc_max=0.9, battery_capacity_kwh=10)
    battery = Battery(config, initial_soc=0.11)
    new_soc, actual_charge, actual_discharge = battery.apply(0, 10, 1)
    assert actual_charge == 0
    assert actual_discharge < 10
    assert new_soc == config.soc_min

    site = SiteModel(config)
    site.battery.soc = 0.11
    result = site.step(10, 0, 0, 10, 0, 0, 0)
    assert result["grid_import_kw"] > 0
    assert result["grid_import_kw"] < 10


def test_flexible_load_is_accounted_as_deferred_or_unmet_energy():
    config = SiteConfig(timestep_minutes=15)
    result = SiteModel(config).step(10, 0, 0, 0, 1, 0, 0)
    assert result["deferred_load_kwh"] == 1.25
    assert result["unmet_load_kwh"] == result["deferred_load_kwh"]
    assert result["served_load_kwh"] + result["unmet_load_kwh"] == 2.5


def test_deferral_penalty_uses_rolling_24_hour_window():
    config = SiteConfig(timestep_minutes=15)
    site = SiteModel(config)
    first = site.step(10, 0, 0, 0, 1, 0, 0)
    for _ in range(95):
        site.step(10, 0, 0, 0, 0, 0, 0)
    after_window = site.step(10, 0, 0, 0, 0, 0, 0)
    assert first["rolling_deferred_energy_kwh"] > 0
    assert after_window["rolling_deferred_energy_kwh"] == 0
