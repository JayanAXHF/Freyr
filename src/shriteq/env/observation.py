"""Shared observation builders for the environment and the RL policy.

Both :mod:`shriteq.env.grid_edge_env` and :mod:`shriteq.control.rl_policy` must
produce byte-identical observations, otherwise a policy trained inside the env
sees a different feature layout at inference time.  Keeping the construction in
one place prevents that drift.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

# Number of scalar features in the ``site_state`` observation vector.  The env's
# observation_space is sized from this constant so a layout change stays in sync.
SITE_STATE_DIM = 12


def build_site_state_vector(
    timestamp: datetime,
    soc: float,
    load_kw: float,
    solar_kw: float,
    billing_peak_kva: float,
    price: float,
    tariff_block: int,
    minutes_to_change: int,
    remaining_shed_budget_kwh: float,
) -> np.ndarray:
    """Return the fixed-order ``site_state`` feature vector.

    Order (see ``SITE_STATE_DIM``):
    ``[hour_sin, hour_cos, weekend, soc, load_kw, solar_kw, billing_peak_kva,
    peak_headroom, remaining_shed_budget_kwh, price, tariff_block,
    minutes_to_change]``.
    """
    hour = timestamp.hour + timestamp.minute / 60.0
    hour_sin = np.sin(2.0 * np.pi * hour / 24.0)
    hour_cos = np.cos(2.0 * np.pi * hour / 24.0)
    weekend = 1.0 if timestamp.weekday() >= 5 else 0.0
    # How much of the billed peak the current net demand already consumes; a
    # small/negative value warns the policy it is about to set a new peak.
    peak_headroom = float(billing_peak_kva) - max(0.0, float(load_kw) - float(solar_kw))
    return np.array(
        [
            hour_sin,
            hour_cos,
            weekend,
            float(soc),
            float(load_kw),
            float(solar_kw),
            float(billing_peak_kva),
            peak_headroom,
            float(remaining_shed_budget_kwh),
            float(price),
            float(tariff_block),
            float(minutes_to_change),
        ],
        dtype=np.float32,
    )


def build_forecast_matrix(load, solar, prices) -> np.ndarray:
    """Return the ``(horizon, 3)`` forecast matrix of (load, solar, price)."""
    return np.column_stack((load, solar, prices)).astype(np.float32)
