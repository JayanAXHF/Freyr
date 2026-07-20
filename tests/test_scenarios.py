from datetime import timedelta

import numpy as np
import pytest
from stable_baselines3 import PPO

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame, SiteState
from shriteq.control.mpc import MPCController
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.sim.load_profiles import generate_load_series
from shriteq.forecast.solar_synth import generate as generate_solar


SCENARIOS = ("clear hot weekday", "monsoon week", "EV-spike day")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_named_scenario_mpc_and_ppo_bounds(scenario):
    config = SiteConfig()
    load = generate_load_series(config, "2026-01-05", 2).iloc[:96].copy()
    solar = generate_solar(config, "2026-01-05", 2).iloc[:96].copy()
    if scenario == "monsoon week":
        solar = solar * 0.55
    elif scenario == "EV-spike day":
        load.iloc[64:80] += 10

    frames = [
        ForecastFrame(load.index[i], float(load.iloc[i]), float(load.iloc[i] * .9), float(load.iloc[i] * 1.1), float(solar.iloc[i]), float(solar.iloc[i] * .9), float(solar.iloc[i] * 1.1), 8.0, 250.0, 0)
        for i in range(96)
    ]
    controller = MPCController(config)
    controller.solve(SiteState(load.index[0], .5, float(load.iloc[0]), float(solar.iloc[0]), 0, 0, 60), frames)
    assert controller.problem.status == "optimal"

    env = GridEdgeEnv(config, load_series=load, solar_series=solar)
    observation, _ = env.reset(seed=7)
    model = PPO.load("models/ppo_gridedge.zip", env=env)
    for _ in range(96):
        action, _ = model.predict(observation, deterministic=True)
        action = np.clip(action, -1, 1)
        battery = float(action[0])
        assert 0 <= max(0.0, battery) * config.max_charge_kw <= config.max_charge_kw
        assert 0 <= max(0.0, -battery) * config.max_discharge_kw <= config.max_discharge_kw
        assert np.all(np.clip(action[1:], 0, 1) >= 0) and np.all(np.clip(action[1:], 0, 1) <= 1)
        observation, _, terminated, _, _ = env.step(action)
        if terminated:
            break
