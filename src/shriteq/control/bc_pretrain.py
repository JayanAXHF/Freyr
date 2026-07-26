"""Behavior-cloning warm start for the PPO dispatch policy.

Pure-RL PPO gets stuck in a "drain the battery, never recharge" local optimum:
discharging pays off immediately while charging costs (energy + a demand-peak
bump) now for a delayed benefit. The MPC controller already solves this by
optimization, so we clone its dispatch into the PPO policy network to seed
training near the good arbitrage behavior, then (optionally) fine-tune with PPO.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

from shriteq.config import SiteConfig
from shriteq.contracts import SiteState
from shriteq.control.mpc import MPCController
from shriteq.env.forecast_provider import SeriesForecastProvider
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.eval.benchmark import _frames, _scenario
from shriteq.control.rl_train import make_env


def _plan_to_action(config: SiteConfig, plan) -> np.ndarray:
    """Map an MPC DispatchPlan to the env's [-1, 1]^4 action (same convention
    as ``benchmark._run_ppo`` and ``grid_edge_env.step``)."""
    battery = (
        -plan.battery_kw / config.max_discharge_kw
        if plan.battery_kw >= 0
        else -plan.battery_kw / config.max_charge_kw
    )
    action = np.array(
        [battery, plan.hvac_fraction, plan.ev_fraction, plan.pump_fraction],
        dtype=np.float32,
    )
    return np.clip(action, -1.0, 1.0)


def collect_mpc_dataset(
    config: SiteConfig, seeds, resolve_every: int = 8
) -> tuple[list[dict], list[np.ndarray]]:
    """Roll out the oracle MPC over several windows, recording (obs, action).

    Observations come from ``env._observation()`` so they are byte-identical to
    what the policy sees at train/inference time; actions come from MPC solving
    on the *actual* load/solar (best demonstrations).
    """
    obs_list: list[dict] = []
    act_list: list[np.ndarray] = []
    for seed in seeds:
        load, solar = _scenario(config, seed)
        provider = SeriesForecastProvider(config, load, solar)
        env = GridEdgeEnv(
            config, load_series=load, solar_series=solar, forecast_provider=provider
        )
        env.reset(seed=0)
        mpc = MPCController(config)
        plan = None
        for pos in range(len(load)):
            observation = env._observation()
            if plan is None or pos % resolve_every == 0:
                remaining = max(
                    0.0,
                    config.deferred_energy_budget_kwh_per_day
                    - sum(env.site.deferred_energy_kwh.values()),
                )
                state = SiteState(
                    load.index[pos],
                    env.site.battery.soc,
                    float(load.iloc[pos]),
                    float(solar.iloc[pos]),
                    env.tariff.current_billing_peak_kva,
                    env.tariff.peek(load.index[pos])[0],
                    env.tariff.peek(load.index[pos])[2],
                    remaining,
                )
                plan = mpc.solve(state, _frames(config, load, solar, pos))
            elif pos % resolve_every != 0:
                hvac, ev, pump = mpc.flex_fractions_at(pos % resolve_every)
                plan.hvac_fraction, plan.ev_fraction, plan.pump_fraction = (
                    hvac,
                    ev,
                    pump,
                )
            action = _plan_to_action(config, plan)
            obs_list.append(
                {
                    key: np.asarray(value, dtype=np.float32)
                    for key, value in observation.items()
                }
            )
            act_list.append(action)
            env.step(action)
        print(
            f"collected window seed={seed} (total samples={len(obs_list)})", flush=True
        )
    return obs_list, act_list


def behavior_clone(
    config: SiteConfig,
    obs_list: list[dict],
    act_list: list[np.ndarray],
    epochs: int = 40,
    batch_size: int = 256,
    lr: float = 1e-3,
    model_path: str | Path = "models/ppo_gridedge_bc",
) -> PPO:
    """Supervised-train the PPO policy to match MPC actions; save model+stats."""
    env = DummyVecEnv([make_env(config)])
    env = VecNormalize(
        env, norm_obs=True, norm_reward=True, clip_obs=10.0, clip_reward=10.0
    )

    # Freeze VecNormalize obs stats onto the demonstration distribution so the
    # BC-normalized observations match what the saved policy will normalize.
    site = np.stack([o["site_state"] for o in obs_list]).astype(np.float64)
    forecast = np.stack([o["forecast"] for o in obs_list]).astype(np.float64)
    env.obs_rms["site_state"].mean = site.mean(axis=0)
    env.obs_rms["site_state"].var = site.var(axis=0) + 1e-8
    env.obs_rms["site_state"].count = float(len(site))
    env.obs_rms["forecast"].mean = forecast.mean(axis=0)
    env.obs_rms["forecast"].var = forecast.var(axis=0) + 1e-8
    env.obs_rms["forecast"].count = float(len(forecast))

    model = PPO(
        "MultiInputPolicy",
        env,
        verbose=0,
        seed=42,
        gamma=0.998,
        gae_lambda=0.95,
        n_steps=2048,
        batch_size=2048,
        n_epochs=10,
        learning_rate=3e-4,
        ent_coef=0.0,
        policy_kwargs=dict(net_arch=dict(pi=[256, 256], vf=[256, 256])),
    )

    device = model.policy.device
    targets = torch.as_tensor(np.stack(act_list), dtype=torch.float32, device=device)
    site_f = site.astype(np.float32)
    forecast_f = forecast.astype(np.float32)
    optimizer = torch.optim.Adam(model.policy.parameters(), lr=lr)

    n = len(obs_list)
    indices = np.arange(n)
    for epoch in range(epochs):
        np.random.shuffle(indices)
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, n, batch_size):
            batch = indices[start : start + batch_size]
            normalized = env.normalize_obs(
                {"site_state": site_f[batch], "forecast": forecast_f[batch]}
            )
            obs_tensor, _ = model.policy.obs_to_tensor(normalized)
            distribution = model.policy.get_distribution(obs_tensor)
            predicted = distribution.distribution.mean
            loss = torch.mean((predicted - targets[batch]) ** 2)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach())
            n_batches += 1
        if epoch % 5 == 0 or epoch == epochs - 1:
            print(
                f"bc epoch={epoch} mse={epoch_loss / max(1, n_batches):.5f}", flush=True
            )

    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))
    env.save(str(model_path) + "_vecnormalize.pkl")
    env.close()
    return model


if __name__ == "__main__":
    cfg = SiteConfig()
    obs, act = collect_mpc_dataset(cfg, seeds=[10, 11, 12])
    behavior_clone(cfg, obs, act)
    print("BC_DONE")
