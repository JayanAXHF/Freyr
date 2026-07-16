"""SARIMAX-based quarter-hourly load forecaster."""

from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame
from shriteq.forecast.solar_synth import generate as generate_solar
from shriteq.forecast.tariff import TariffModel


def _calendar_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    hour = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    return pd.DataFrame(
        {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "day_of_week": index.dayofweek.to_numpy(),
            "weekend": (index.dayofweek.to_numpy() >= 5).astype(float),
        },
        index=index,
    )


class LoadForecaster:
    """Fit a seasonal SARIMAX model and produce complete forecast contracts."""

    def __init__(self, config: SiteConfig | None = None):
        self.config = config or SiteConfig()
        self._result = None
        self._last_timestamp: pd.Timestamp | None = None
        self._residual_scale = 1.0

    def fit(self, historical_series: pd.Series) -> "LoadForecaster":
        series = pd.Series(historical_series, dtype=float).dropna()
        if len(series) < 2 * 96:
            raise ValueError("at least two days of history are required")
        if not isinstance(series.index, pd.DatetimeIndex):
            raise TypeError("historical_series must have a DatetimeIndex")
        series = series.sort_index()
        exog = _calendar_features(series.index)
        self._result = SARIMAX(
            series,
            exog=exog,
            order=(1, 0, 1),
            seasonal_order=(1, 0, 1, 96),
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(method="powell")
        residuals = np.asarray(self._result.resid, dtype=float)
        self._residual_scale = max(float(np.nanstd(residuals)), 0.1)
        self._last_timestamp = series.index[-1]
        return self

    def predict(self, n_steps: int) -> list[ForecastFrame]:
        if self._result is None or self._last_timestamp is None:
            raise RuntimeError("fit must be called before predict")
        if n_steps < 1:
            raise ValueError("n_steps must be positive")
        frequency = pd.Timedelta(minutes=self.config.timestep_minutes)
        timestamps = pd.date_range(
            start=self._last_timestamp + frequency,
            periods=n_steps,
            freq=frequency,
        )
        forecast = self._result.get_forecast(
            steps=n_steps,
            exog=_calendar_features(timestamps),
        )
        mean = np.maximum(0.0, np.asarray(forecast.predicted_mean, dtype=float))
        interval = np.asarray(forecast.conf_int(alpha=0.20), dtype=float)
        p10 = np.maximum(0.0, interval[:, 0])
        p90 = np.maximum(p10, interval[:, 1])

        solar = generate_solar(self.config, timestamps[0], (n_steps + 95) // 96)
        tariff = TariffModel(self.config)
        frames = []
        for index, timestamp in enumerate(timestamps):
            tariff_info = tariff.step(timestamp, 0.0)
            frames.append(
                ForecastFrame(
                    timestamp=timestamp,
                    load_mean_kw=float(mean[index]),
                    load_p10_kw=float(p10[index]),
                    load_p90_kw=float(p90[index]),
                    solar_mean_kw=float(solar.iloc[index]),
                    solar_p10_kw=float(solar.iloc[index] * 0.9),
                    solar_p90_kw=float(solar.iloc[index] * 1.1),
                    price_inr_per_kwh=float(tariff_info["tod_price_inr_per_kwh"]),
                    demand_rate_inr_per_kva=float(
                        self.config.demand_charge_inr_per_kva_month
                    ),
                    tariff_block_id=int(tariff_info["tariff_block_id"]),
                )
            )
        return frames
