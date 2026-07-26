"""Synthetic site-load profiles."""

from __future__ import annotations

import numpy as np
import pandas as pd

from shriteq.config import SiteConfig


def generate_load_series(config: SiteConfig, start, days: int) -> pd.Series:
    """Generate a noisy, synthetic site-load series at the configured timestep."""
    periods = days * (24 * 60 // config.timestep_minutes)
    index = pd.date_range(
        start=start, periods=periods, freq=f"{config.timestep_minutes}min", tz=config.tz
    )
    hours = index.hour.to_numpy() + index.minute.to_numpy() / 60.0

    base = 3.0
    morning_peak = 5.0 * np.exp(-0.5 * ((hours - 8.0) / 1.8) ** 2)
    evening_peak = 7.0 * np.exp(-0.5 * ((hours - 19.0) / 2.2) ** 2)
    overnight = 1.0 * np.exp(-0.5 * ((hours - 2.0) / 2.5) ** 2)
    weekday_scale = np.where(index.dayofweek.to_numpy() >= 5, 0.72, 1.0)
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 0.35, periods)
    load_kw = np.maximum(
        0.1, (base + morning_peak + evening_peak + overnight) * weekday_scale + noise
    )

    return pd.Series(load_kw, index=index, name="load_kw")


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    series = generate_load_series(SiteConfig(), "2026-01-05", days=7)
    series.plot(figsize=(12, 4), title="Synthetic weekly load profile")
    plt.ylabel("Load (kW)")
    plt.tight_layout()
    plt.savefig("/tmp/load_check.png")
