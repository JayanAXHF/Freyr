"""Gymnasium wrapper for the si pte simulator."""

import gymnasium as gym
import numpy as np

from shriteq.config import SiteConfig
from shriteq.forecast.tariff import TariffModel
from shriteq.sim.load_source import resolve_full_series, resolve_solar_for
from shriteq.sim.site_model import SiteModel
from shriteq.env.reward import compute_reward, deferred_penalty, peak_potential
from shriteq.env.forecast_provider import LoadForecasterProvider
from shriteq.env.observation import (
    SITE_STATE_DIM,
    build_forecast_matrix,
    build_site_state_vector,
)


class GridEdgeEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        config: SiteConfig | None = None,
        load_series=None,
        solar_series=None,
        horizon: int = 96,
        forecast_provider=None,
    ):
        super().__init__()
        self.config = config or SiteConfig()
        self.horizon = horizon
        self.load_series = (
            load_series
            if load_series is not None
            else resolve_full_series(self.config)
        )
        self.solar_series = (
            solar_series
            if solar_series is not None
            else resolve_solar_for(self.config, self.load_series, "2026-01-01", 90)
        )
        if self.load_series.index.tz != self.solar_series.index.tz:
            raise ValueError(
                "load and solar series must use the same timezone-aware index"
            )
        self.forecast_provider = forecast_provider or LoadForecasterProvider(
            self.config, self.load_series, self.solar_series
        )
        self.site = SiteModel(self.config)
        self.tariff = TariffModel(self.config)
        self.action_space = gym.spaces.Box(-1.0, 1.0, shape=(4,), dtype=np.float32)
        self.observation_space = gym.spaces.Dict(
            {
                "site_state": gym.spaces.Box(
                    -np.inf, np.inf, shape=(SITE_STATE_DIM,), dtype=np.float32
                ),
                "forecast": gym.spaces.Box(
                    -np.inf, np.inf, shape=(horizon, 3), dtype=np.float32
                ),
            }
        )
        self._position = 0
        self._episode_end = 0
        self._prev_potential = 0.0

    def _observation(self):
        observation_position = min(self._position, len(self.load_series) - 1)
        load, solar, prices = self.forecast_provider.forecast(
            observation_position, self.horizon
        )
        forecast = build_forecast_matrix(load, solar, prices)
        timestamp = self.load_series.index[observation_position]
        tariff_block_id, price, minutes = self.tariff.peek(timestamp)
        remaining_shed_budget_kwh = max(
            0.0,
            self.config.deferred_energy_budget_kwh_per_day
            - sum(self.site.deferred_energy_kwh.values()),
        )
        state = build_site_state_vector(
            timestamp=timestamp,
            soc=self.site.battery.soc,
            load_kw=float(self.load_series.iloc[observation_position]),
            solar_kw=float(self.solar_series.iloc[observation_position]),
            billing_peak_kva=self.tariff.current_billing_peak_kva,
            price=price,
            tariff_block=tariff_block_id,
            minutes_to_change=minutes,
            remaining_shed_budget_kwh=remaining_shed_budget_kwh,
        )
        return {"site_state": state, "forecast": forecast}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        max_start = len(self.load_series) - self.config.episode_days * 96 - 1
        self._position = int(self.np_random.integers(0, max(1, max_start + 1)))
        self._episode_end = self._position + self.config.episode_days * 96
        self.site = SiteModel(self.config)
        self.tariff = TariffModel(self.config)
        self._prev_potential = 0.0
        return self._observation(), {}

    def step(self, action):
        action = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        battery = float(action[0])
        charge = max(0.0, battery) * self.config.max_charge_kw
        discharge = max(0.0, -battery) * self.config.max_discharge_kw
        # Neutral/negative actions mean "do not shed"; shedding must be chosen
        # explicitly by pushing an action positive. This keeps an untrained or
        # entropy-exploring policy at ~zero shedding instead of the old 50%,
        # which alone saturated the daily shed budget.
        flex = np.clip(action[1:], 0.0, 1.0)
        timestamp = self.load_series.index[self._position]
        result = self.site.step(
            self.load_series.iloc[self._position],
            self.solar_series.iloc[self._position],
            charge,
            discharge,
            *flex,
        )
        tariff = self.tariff.step(timestamp, result["grid_import_kw"])
        reward = compute_reward(
            self.config,
            result["grid_import_kwh"],
            tariff["tod_price_inr_per_kwh"],
            tariff["peak_bump_kva"],
            self.config.demand_charge_inr_per_kva_month,
            result["unmet_load_kwh"],
            result["battery_throughput_kwh"],
            result["rolling_deferred_energy_kwh"],
            result["shed_load_kwh"],
        )
        # Optional potential-based shaping (default off -> contributes 0).
        potential = peak_potential(self.config, result["grid_import_kw"])
        reward += potential - self._prev_potential
        self._prev_potential = potential
        self._position += 1
        terminated = self._position >= self._episode_end
        info = {
            **result,
            **tariff,
            "bill_delta_inr": tariff["tod_price_inr_per_kwh"]
            * result["grid_import_kwh"],
            "deferred_penalty": deferred_penalty(
                self.config, result["rolling_deferred_energy_kwh"]
            ),
        }
        return self._observation(), float(reward), terminated, False, info
