"""PPO smoke-training entry point for the GridEdge environment."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor

from shriteq.config import SiteConfig
from shriteq.env.grid_edge_env import GridEdgeEnv


class EpisodeRewardLogger(BaseCallback):
    """Record mean completed-episode reward while PPO trains."""

    def __init__(self):
        super().__init__()
        self.episode_rewards: list[float] = []
        self.log_path = Path("outputs/ppo_training_rewards.csv")

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            episode = info.get("episode")
            if episode is not None:
                self.episode_rewards.append(float(episode["r"]))
                mean_reward = float(np.mean(self.episode_rewards))
                self.logger.record("rollout/mean_episode_reward", mean_reward)
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", newline="") as stream:
                    csv.writer(stream).writerow([len(self.episode_rewards), float(episode["r"]), mean_reward])
                print(f"episode={len(self.episode_rewards)} mean_episode_reward={mean_reward:.3f}")
        return True


def train(total_timesteps: int = 50_000, model_path: str | Path = "models/ppo_gridedge") -> PPO:
    """Train PPO and save it; returns the fitted model for callers/tests."""
    reward_log = Path("outputs/ppo_training_rewards.csv")
    if reward_log.exists():
        reward_log.unlink()
    env = Monitor(GridEdgeEnv(SiteConfig()))
    model = PPO("MultiInputPolicy", env, verbose=0, seed=42)
    callback = EpisodeRewardLogger()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))
    return model


if __name__ == "__main__":
    train()
