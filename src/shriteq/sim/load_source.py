"""Single indirection point between the synthetic load/solar generators and an
optional real metered feed.

When ``config.meter_feed_path`` is ``None`` every function here falls through to
the exact synthetic call it replaces, so the existing pipeline is byte-for-byte
unchanged. When a feed is configured, windows are drawn from the feed's own
timeline (a real feed has no relationship to the synthetic anchor dates like
2026-01-01), and solar -- which stays synthetic -- is generated aligned to
whatever timestamps the feed actually has.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache

import pandas as pd

from shriteq.config import SiteConfig
from shriteq.forecast.solar_synth import generate as generate_solar
from shriteq.sim.load_profiles import generate_load_series
from shriteq.sim.meter_feed import load_meter_series

# Minimum trailing history (in steps) required before a requested `before_ts`
# for resolve_history to succeed against a feed, rather than silently
# fabricating data or clamping to something too short to fit a SARIMAX model.
MIN_HISTORY_STEPS = 2 * 96

# The forecaster always asks for this many days of lookback (see
# forecast_provider._fit_cached_forecast). Synthetic generation can fabricate
# dates before a series' own start for free; a feed cannot, so
# resolve_full_series reserves this many leading days of a configured feed as
# lookback-only, never exposing them as part of the usable load series.
FORECAST_HISTORY_DAYS = 21


def _periods_per_day(config: SiteConfig) -> int:
    return 24 * 60 // config.timestep_minutes


@lru_cache(maxsize=8)
def _load_feed_cached(
    path: str,
    mtime: float,
    timestep_minutes: int,
    tz: str,
    timestamp_column: str | None,
    value_column: str | None,
    max_gap_steps: int,
) -> pd.Series:
    config = SiteConfig(
        timestep_minutes=timestep_minutes,
        tz=tz,
        meter_max_gap_steps=max_gap_steps,
    )
    return load_meter_series(
        path,
        config,
        timestamp_column=timestamp_column,
        value_column=value_column,
    )


def _feed(config: SiteConfig) -> pd.Series | None:
    if config.meter_feed_path is None:
        return None
    mtime = os.stat(config.meter_feed_path).st_mtime
    return _load_feed_cached(
        config.meter_feed_path,
        mtime,
        config.timestep_minutes,
        config.tz,
        config.meter_timestamp_column,
        config.meter_value_column,
        config.meter_max_gap_steps,
    )


def resolve_full_series(config: SiteConfig) -> pd.Series:
    """Whole-feed load for GridEdgeEnv's default 90-day synthetic window.

    When a feed is configured, its first ``FORECAST_HISTORY_DAYS`` are reserved
    as lookback-only history for the forecaster (see ``resolve_history``) and
    excluded from the returned series -- the env's own first timestamp always
    has real feed history preceding it, mirroring how synthetic generation can
    fabricate lookback before its own start for free.
    """
    feed = _feed(config)
    if feed is not None:
        reserve = FORECAST_HISTORY_DAYS * _periods_per_day(config)
        if len(feed) <= reserve:
            raise ValueError(
                f"Meter feed at {config.meter_feed_path!r} has only {len(feed)} "
                f"steps, not enough to reserve {reserve} steps of forecaster "
                "lookback plus a usable series."
            )
        return feed.iloc[reserve:]
    return generate_load_series(config, "2026-01-01", 90)


def resolve_history(config: SiteConfig, before_ts, days: int) -> pd.Series:
    """The ``days`` of load immediately preceding ``before_ts`` (exclusive).

    Used for SARIMAX forecaster fitting. Against a feed, clamps to whatever
    history is available rather than erroring, unless there isn't even
    ``MIN_HISTORY_STEPS`` of it.
    """
    feed = _feed(config)
    if feed is None:
        before_ts = pd.Timestamp(before_ts)
        if before_ts.tzinfo is not None:
            before_ts = before_ts.tz_localize(None)
        return generate_load_series(config, before_ts - pd.Timedelta(days=days), days)

    before_ts = pd.Timestamp(before_ts)
    if before_ts.tzinfo is None:
        before_ts = before_ts.tz_localize(config.tz)
    else:
        before_ts = before_ts.tz_convert(config.tz)

    history = feed.loc[feed.index < before_ts]
    if len(history) < MIN_HISTORY_STEPS:
        raise ValueError(
            f"Meter feed has only {len(history)} steps of history before "
            f"{before_ts}; need at least {MIN_HISTORY_STEPS} to fit a forecast."
        )
    periods = days * _periods_per_day(config)
    return history.iloc[-periods:]


def resolve_slice(
    config: SiteConfig, synthetic_start, days: int, *, edge: str = "head"
) -> pd.Series:
    """A fixed-length window used for eval/training/dashboard defaults.

    ``edge`` picks which end of a configured feed to take from ("head" or
    "tail"); it's ignored in synthetic mode, where ``synthetic_start`` is used
    verbatim exactly as it is today.
    """
    feed = _feed(config)
    if feed is None:
        return generate_load_series(config, synthetic_start, days)

    periods = days * _periods_per_day(config)
    if edge == "head":
        return feed.iloc[:periods].copy()
    if edge == "tail":
        return feed.iloc[-periods:].copy()
    raise ValueError(f"edge must be 'head' or 'tail', got {edge!r}")


def resolve_solar_for(
    config: SiteConfig, load_series: pd.Series, synthetic_start, synthetic_days: int
) -> pd.Series:
    """Synthetic solar aligned to whatever timestamps ``load_series`` actually has.

    In synthetic mode this reproduces today's call exactly. In feed mode, solar
    stays synthetic but is generated starting at the feed's own first
    timestamp so length and dates match the load series.
    """
    if config.meter_feed_path is None:
        return generate_solar(config, synthetic_start, synthetic_days)

    periods_per_day = _periods_per_day(config)
    days = math.ceil(len(load_series) / periods_per_day)
    solar = generate_solar(config, load_series.index[0], days)
    solar = solar.iloc[: len(load_series)]
    solar.index = load_series.index
    return solar
