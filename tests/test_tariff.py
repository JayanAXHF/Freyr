from datetime import datetime, timedelta

from shriteq.config import SiteConfig
from shriteq.forecast.tariff import TariffModel


def test_billing_peak_only_bumps_when_a_new_peak_is_set():
    model = TariffModel(SiteConfig())
    timestamp = datetime(2026, 1, 1, 9)
    imports = [5.0, 8.0, 12.0, 9.0, 12.0, 4.0]
    results = [model.step(timestamp + timedelta(minutes=15 * i), value) for i, value in enumerate(imports)]

    peaks = [result["current_billing_peak_kva"] for result in results]
    bumps = [result["peak_bump_kva"] for result in results]
    assert peaks == [5.0, 8.0, 12.0, 12.0, 12.0, 12.0]
    assert bumps == [5.0, 3.0, 4.0, 0.0, 0.0, 0.0]
