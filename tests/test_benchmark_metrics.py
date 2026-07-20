import pandas as pd

from shriteq.config import SiteConfig
from shriteq.eval.benchmark import _metrics


def test_solar_self_consumption_reflects_curtailment():
    config = SiteConfig()
    rows = [{"energy_cost": 0.0, "grid_import_kw": 0.0, "unmet_load_kwh": 0.0, "solar_used_kwh": 1.0}]
    metrics = _metrics(config, rows, pd.Series([16.0]))
    assert metrics["solar_self_consumption"] == 0.25
