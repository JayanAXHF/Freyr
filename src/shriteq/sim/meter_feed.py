"""Load a real historical meter feed (CSV/Parquet) into the canonical load-series
contract used throughout the pipeline: tz-aware 15-minute ``pd.Series``, float kW,
name ``"load_kw"``, non-negative, regular frequency."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from shriteq.config import SiteConfig


def _read_table(path: str | Path) -> pd.DataFrame:
    suffix = Path(path).suffix.lower()
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported meter feed file type: {path!r} (expected .csv or .parquet)")


def _resolve_columns(
    frame: pd.DataFrame, timestamp_column: str | None, value_column: str | None
) -> tuple[str, str]:
    if timestamp_column is not None and value_column is not None:
        return timestamp_column, value_column

    ts_col = timestamp_column
    if ts_col is None:
        for column in frame.columns:
            try:
                pd.to_datetime(frame[column])
            except (ValueError, TypeError):
                continue
            ts_col = column
            break
        if ts_col is None:
            raise ValueError(
                "Could not auto-detect a timestamp column in the meter feed; "
                "pass timestamp_column explicitly."
            )

    val_col = value_column
    if val_col is None:
        candidates = [
            column
            for column in frame.columns
            if column != ts_col and pd.api.types.is_numeric_dtype(frame[column])
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Could not auto-detect a single numeric load column in the meter "
                f"feed (candidates: {candidates}); pass value_column explicitly."
            )
        val_col = candidates[0]

    return ts_col, val_col


def load_meter_series(
    path: str | Path,
    config: SiteConfig,
    *,
    timestamp_column: str | None = None,
    value_column: str | None = None,
) -> pd.Series:
    """Read a CSV/Parquet meter export and resample it onto the configured grid."""
    frame = _read_table(path)
    ts_col, val_col = _resolve_columns(frame, timestamp_column, value_column)

    timestamps = pd.to_datetime(frame[ts_col])
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize(config.tz)
    else:
        timestamps = timestamps.dt.tz_convert(config.tz)

    series = pd.Series(frame[val_col].to_numpy(dtype=float), index=pd.DatetimeIndex(timestamps))
    series = series.sort_index()
    series = series[~series.index.duplicated(keep="first")]

    max_gap = config.meter_max_gap_steps
    resampled = series.resample(f"{config.timestep_minutes}min").mean()
    resampled = resampled.interpolate(limit=max_gap, limit_area="inside")
    resampled = resampled.ffill(limit=max_gap).bfill(limit=max_gap)

    if resampled.isna().any():
        gap_start = resampled[resampled.isna()].index[0]
        raise ValueError(
            f"Meter feed has a gap wider than meter_max_gap_steps={max_gap} "
            f"starting at {gap_start}; fill it or raise meter_max_gap_steps."
        )
    if resampled.empty:
        raise ValueError(f"Meter feed at {path!r} produced an empty series after resampling.")

    resampled = resampled.clip(lower=0.0).astype(float)
    resampled.name = "load_kw"
    return resampled
