from datetime import datetime, timedelta

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame, SiteState
from shriteq.control.mpc import MPCController


def test_mpc_returns_a_bounded_first_step():
    config = SiteConfig()
    start = datetime(2026, 1, 1)
    frames = [
        ForecastFrame(start + timedelta(minutes=15 * i), 20, 15, 25, 5, 0, 8, 8, 250, 0)
        for i in range(96)
    ]
    controller = MPCController(config)
    plan = controller.solve(SiteState(start, 0.5, 20, 5, 0, 0, 60), frames)
    assert controller.problem is not None
    assert controller.problem.status == "optimal"
    assert 0 <= plan.grid_import_kw
    assert -config.max_charge_kw <= plan.battery_kw <= config.max_discharge_kw
    assert 0 <= plan.hvac_fraction <= 1
    assert 0 <= plan.ev_fraction <= 1
    assert 0 <= plan.pump_fraction <= 1
