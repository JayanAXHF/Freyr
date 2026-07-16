"""Synthetic rooftop-solar generation based on clear-sky irradiance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

from shriteq.config import SiteConfig


def generate(config: SiteConfig, start, days: int) -> pd.Series:
    """Generate a synthetic solar-power series in kW."""
    periods = days * (24 * 60 // config.timestep_minutes)
    times = pd.date_range(
        start=start,
        periods=periods,
        freq=f"{config.timestep_minutes}min",
        tz=config.tz,
    )
    location = pvlib.location.Location(config.lat, config.lon, tz=config.tz)
    clear_sky = location.get_clearsky(times, model="ineichen")
    solar_position = location.get_solarposition(times)
    irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=config.lat,
        surface_azimuth=180,
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
        dni=clear_sky["dni"],
        ghi=clear_sky["ghi"],
        dhi=clear_sky["dhi"],
        model="isotropic",
    )

    month_derate = {
        1: 0.92, 2: 0.93, 3: 0.90, 4: 0.86, 5: 0.83,
        6: 0.65, 7: 0.55, 8: 0.60, 9: 0.72, 10: 0.85,
        11: 0.90, 12: 0.95,
    }
    derate = np.array([month_derate[month] for month in times.month])
    rng = np.random.default_rng(42)
    cloud = np.empty(periods)
    cloud[0] = 1.0
    cloud_noise = rng.normal(0.0, 0.06, periods)
    for index in range(1, periods):
        cloud[index] = np.clip(0.9 * cloud[index - 1] + cloud_noise[index], 0.3, 1.0)

    solar_kw = np.maximum(0.0, irradiance["poa_global"].to_numpy() / 1000.0 * derate * cloud * 10.0)
    return pd.Series(solar_kw, index=times, name="solar_kw")


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    generate(SiteConfig(), "2026-01-05", 7).plot(figsize=(12, 4), title="Synthetic weekly solar profile")
    plt.ylabel("Solar generation (kW)")
    plt.tight_layout()
    plt.savefig("/tmp/solar_check.png")
