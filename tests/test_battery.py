from shriteq.config import SiteConfig
from shriteq.sim.battery import Battery


def test_battery_stays_within_soc_bounds():
    battery = Battery(SiteConfig(), initial_soc=0.5)
    for _ in range(100):
        assert battery.apply(1_000, 0, 1) <= 0.9
    for _ in range(100):
        assert battery.apply(0, 1_000, 1) >= 0.1


def test_full_charge_discharge_cycle_loses_energy_to_efficiency():
    config = SiteConfig(battery_capacity_kwh=10, soc_min=0.0, soc_max=1.0, max_charge_kw=10, max_discharge_kw=10)
    battery = Battery(config, initial_soc=0.0)
    battery.apply(10, 0, 1)
    # 10 kWh charged at sqrt(0.8), then 8 kWh discharged, leaves the
    # expected round-trip loss in the battery.
    final_soc = battery.apply(0, 8, 1)
    assert 0.09 < final_soc < 0.11
