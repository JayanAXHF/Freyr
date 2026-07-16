"""SARIMAX load forecaster with uncertainty bands."""

from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


class SARIMAXForecaster:
    """Forecast quarter-hourly load and retain a held-out evaluation path."""

    def __init__(self, order=(1, 0, 1), seasonal_order=(1, 0, 1, 96)):
        self.order = order
        self.seasonal_order = seasonal_order
        self._result = None
        self.training_series: pd.Series | None = None

    def fit(self, series: pd.Series) -> "SARIMAXForecaster":
        values = pd.Series(series, dtype=float).dropna()
        if len(values) < 2 * self.seasonal_order[-1]:
            raise ValueError("SARIMAX training data must contain at least two daily cycles")
        self.training_series = values
        self._result = SARIMAX(
            values,
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)
        return self

    def predict(self, horizon: int) -> pd.DataFrame:
        if self._result is None:
            raise RuntimeError("fit must be called before predict")
        if horizon < 1:
            raise ValueError("horizon must be positive")
        forecast = self._result.get_forecast(steps=horizon)
        mean = np.maximum(0.0, np.asarray(forecast.predicted_mean, dtype=float))
        interval = forecast.conf_int(alpha=0.20)
        lower = np.maximum(0.0, np.asarray(interval.iloc[:, 0], dtype=float))
        upper = np.maximum(lower, np.asarray(interval.iloc[:, 1], dtype=float))
        index = forecast.predicted_mean.index
        return pd.DataFrame(
            {"load_mean_kw": mean, "load_p10_kw": lower, "load_p90_kw": upper},
            index=index,
        )


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    from shriteq.config import SiteConfig
    from shriteq.sim.load_profiles import generate_load_series

    series = generate_load_series(SiteConfig(), "2026-01-05", days=35)
    train, actual = series.iloc[:-7 * 96], series.iloc[-7 * 96:]
    prediction = SARIMAXForecaster().fit(train).predict(len(actual))
    coverage = ((actual >= prediction["load_p10_kw"]) & (actual <= prediction["load_p90_kw"])).mean()
    print(f"held-out p10-p90 coverage: {coverage:.1%}")
    ax = actual.plot(figsize=(13, 4), label="actual", color="black")
    prediction["load_mean_kw"].plot(ax=ax, label="forecast")
    ax.fill_between(prediction.index, prediction["load_p10_kw"], prediction["load_p90_kw"], alpha=0.25, label="p10-p90")
    ax.legend()
    ax.set_ylabel("Load (kW)")
    plt.tight_layout()
    plt.savefig("/tmp/sarimax_check.png")
