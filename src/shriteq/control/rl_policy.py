"""Stable-Baselines3 policy adapter using the common dispatch contract."""

from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.monitor import Monitor

from shriteq.config import SiteConfig
from shriteq.contracts import DispatchPlan, ForecastFrame, SiteState
from shriteq.env.grid_edge_env import GridEdgeEnv


class RLPolicy:
    def __init__(self, config: SiteConfig, model_path: str | Path, horizon: int = 16):
        self.config = config
        self.horizon = horizon
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"PPO model not found at {path}; run rl_train.train() first"
            )
        stats_base = path.with_suffix("") if path.suffix == ".zip" else path
        stats_path = Path(str(stats_base) + "_vecnormalize.pkl")
        if not stats_path.exists():
            raise FileNotFoundError(
                f"PPO normalization stats not found at {stats_path}; retrain with rl_train.train()"
            )
        vec_env = DummyVecEnv([lambda: Monitor(GridEdgeEnv(config))])
        self.vec_env = VecNormalize.load(str(stats_path), vec_env)
        self.vec_env.training = False
        self.vec_env.norm_reward = False
        self.model = PPO.load(str(path), env=self.vec_env)

    def solve(
        self, site_state: SiteState, forecast_frames: list[ForecastFrame]
    ) -> DispatchPlan:
        if not forecast_frames:
            raise ValueError("forecast_frames must not be empty")
        frames = forecast_frames[: self.horizon]
        if len(frames) < self.horizon:
            raise ValueError(f"RLPolicy requires {self.horizon} forecast frames")
        forecast = np.array(
            [
                [frame.load_mean_kw, frame.solar_mean_kw, frame.price_inr_per_kwh]
                for frame in frames
            ],
            dtype=np.float32,
        )
        first = frames[0]
        observation = {
            "site_state": np.array(
                [
                    site_state.timestamp.hour,
                    site_state.soc,
                    site_state.current_load_kw,
                    site_state.current_solar_kw,
                    site_state.current_billing_peak_kva,
                    site_state.current_tariff_block,
                    site_state.minutes_to_tariff_change,
                ],
                dtype=np.float32,
            ),
            "forecast": forecast,
        }
        normalized = self.vec_env.normalize_obs(
            {key: np.expand_dims(value, axis=0) for key, value in observation.items()}
        )
        action, _ = self.model.predict(normalized, deterministic=True)
        action = np.clip(np.asarray(action, dtype=np.float32).reshape(-1), -1.0, 1.0)
        battery = float(action[0])
        flex = (action[1:] + 1.0) / 2.0
        return DispatchPlan(
            step=0,
            battery_kw=max(0.0, -battery) * self.config.max_discharge_kw
            - max(0.0, battery) * self.config.max_charge_kw,
            hvac_fraction=float(flex[0]),
            ev_fraction=float(flex[1]),
            pump_fraction=float(flex[2]),
            grid_import_kw=max(0.0, first.load_mean_kw - first.solar_mean_kw),
            predicted_peak_kva=site_state.current_billing_peak_kva,
        )
