"""Forecast providers used by the environment and benchmark harness."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import pandas as pd

from shriteq.config import SiteConfig
from shriteq.forecast.load_forecaster import LoadForecaster
from shriteq.forecast.tariff import TariffModel
from shriteq.sim.load_source import FORECAST_HISTORY_DAYS, resolve_history


class SeriesForecastProvider:
    """Provider backed by an explicit forecast series (oracle when desired)."""

    def __init__(self, config: SiteConfig, load, solar):
        self.config = config
        self.load = load
        self.solar = solar
        self.tariff = TariffModel(config)

    def forecast(self, position: int, horizon: int):
        end = min(position + horizon, len(self.load))
        load = self.load.iloc[position:end].to_numpy(dtype=float)
        solar = self.solar.iloc[position:end].to_numpy(dtype=float)
        if len(load) < horizon:
            load = np.pad(load, (0, horizon - len(load)), mode="edge")
            solar = np.pad(solar, (0, horizon - len(solar)), mode="edge")
        prices = []
        for offset in range(horizon):
            index = min(position + offset, len(self.load) - 1)
            _, price, _ = self.tariff.peek(self.load.index[index])
            prices.append(price)
        return load, solar, np.asarray(prices, dtype=float)


@lru_cache(maxsize=8)
def _fit_cached_forecast(config_key: tuple, start: str, periods: int) -> np.ndarray:
    # config_key[7] (feed mtime) is not used to build the config -- it exists
    # only so the lru_cache key changes when the feed file is rewritten.
    config = SiteConfig(
        timestep_minutes=config_key[0],
        tz=config_key[1],
        unmet_penalty=config_key[2],
        meter_feed_path=config_key[3],
        meter_timestamp_column=config_key[4],
        meter_value_column=config_key[5],
        meter_max_gap_steps=config_key[6],
    )
    history = resolve_history(config, pd.Timestamp(start), FORECAST_HISTORY_DAYS)
    frames = LoadForecaster(config).fit(history).predict(periods)
    return np.asarray([frame.load_mean_kw for frame in frames], dtype=float)


class LoadForecasterProvider(SeriesForecastProvider):
    """Use SARIMAX load forecasts while retaining the supplied solar trace."""

    def __init__(self, config: SiteConfig, load, solar):
        super().__init__(config, load, solar)
        feed_mtime = (
            os.stat(config.meter_feed_path).st_mtime
            if config.meter_feed_path is not None
            else None
        )
        key = (
            config.timestep_minutes,
            config.tz,
            config.unmet_penalty,
            config.meter_feed_path,
            config.meter_timestamp_column,
            config.meter_value_column,
            config.meter_max_gap_steps,
            feed_mtime,
        )
        values = _fit_cached_forecast(key, str(load.index[0]), len(load))
        self.load = pd.Series(values, index=load.index, name="forecast_load_kw")
