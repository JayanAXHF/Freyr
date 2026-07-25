"""PPO training entry point for the GridEdge (Freyr) environment."""

from __future__ import annotations

import csv
import shutil
from collections import deque
from pathlib import Path
from typing import Callable

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize

from shriteq.config import SiteConfig
from shriteq.env.grid_edge_env import GridEdgeEnv
from shriteq.sim.load_source import resolve_slice, resolve_solar_for


def make_env(config: SiteConfig) -> Callable[[], Monitor]:
    """Return a picklable factory building a Monitor-wrapped training env."""

    def _init() -> Monitor:
        return Monitor(GridEdgeEnv(config, horizon=96))

    return _init


def _linear_schedule(initial: float) -> Callable[[float], float]:
    """SB3 schedule: ``progress_remaining`` goes 1 -> 0 over training."""

    def _schedule(progress_remaining: float) -> float:
        return progress_remaining * initial

    return _schedule


def _build_eval_env(config: SiteConfig) -> VecNormalize:
    """A deterministic held-out eval env (single fixed 30-day window).

    A length ``episode_days*96`` series makes ``reset`` start at 0 every time
    (``max_start = -1``), so eval reward is comparable across checkpoints. The
    start date is disjoint from the default training window (2026-01-01).
    """
    steps = config.episode_days * 96
    load = resolve_slice(config, "2026-06-01", config.episode_days, edge="tail")
    solar = resolve_solar_for(config, load, "2026-06-01", config.episode_days)
    load = load.iloc[:steps]
    solar = solar.iloc[:steps]

    def _init() -> Monitor:
        # Default LoadForecasterProvider so eval obs matches training.
        return Monitor(
            GridEdgeEnv(config, load_series=load, solar_series=solar, horizon=96)
        )

    eval_env = VecNormalize(
        DummyVecEnv([_init]),
        norm_obs=True,
        norm_reward=False,
        clip_obs=10.0,
        training=False,
    )
    return eval_env


class EpisodeRewardLogger(BaseCallback):
    """Record a rolling-window mean completed-episode reward while training.

    The previous version logged a *cumulative* mean over all episodes, which
    only ever drifts upward and hides whether the recent policy is improving.
    """

    def __init__(self, window: int = 100):
        super().__init__()
        self.episode_rewards: deque[float] = deque(maxlen=window)
        self.count = 0
        self.log_path = Path("outputs/ppo_training_rewards.csv")

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            episode = info.get("episode")
            if episode is not None:
                self.count += 1
                self.episode_rewards.append(float(episode["r"]))
                mean_reward = float(np.mean(self.episode_rewards))
                self.logger.record("rollout/mean_episode_reward", mean_reward)
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", newline="") as stream:
                    csv.writer(stream).writerow(
                        [self.count, float(episode["r"]), mean_reward]
                    )
                print(
                    f"episode={self.count} "
                    f"rolling_mean_reward({len(self.episode_rewards)})={mean_reward:.3f}"
                )
        return True


def train(
    total_timesteps: int = 4_000_000,
    model_path: str | Path = "models/ppo_gridedge",
    n_envs: int = 1,
    config: SiteConfig | None = None,
) -> PPO:
    """Train PPO and save it to ``model_path``; returns the fitted model.

    Uses a raised discount (``gamma=0.998``) so intraday battery arbitrage is
    credited well past the ~1-day horizon of the SB3 default, parallel envs for
    throughput, and an ``EvalCallback`` on a held-out window to keep the *best*
    policy rather than the last. ``config`` defaults to ``SiteConfig()``
    (synthetic load); pass one with ``meter_feed_path`` set to train against a
    real feed instead.
    """
    reward_log = Path("outputs/ppo_training_rewards.csv")
    if reward_log.exists():
        reward_log.unlink()

    config = config or SiteConfig()
    # Default n_envs=1 (in-process DummyVecEnv): each SubprocVecEnv worker is a
    # separate interpreter importing PyTorch (~1-2 GB RSS each), which OOM-crashes
    # an 8 GB Mac at n_envs=4. Only raise n_envs on a machine with ample RAM
    # (>=16 GB); single-env training is memory-safe and still ~2.3 h for 4M steps.
    vec_cls = SubprocVecEnv if n_envs > 1 else DummyVecEnv
    env = vec_cls([make_env(config) for _ in range(n_envs)])
    env = VecNormalize(
        env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
        # Standard clip for normalized rewards. If the sparse demand-charge
        # spike appears washed out in training, disable reward clipping.
        clip_reward=10.0,
    )

    eval_env = _build_eval_env(config)
    models_dir = Path(model_path).parent
    models_dir.mkdir(parents=True, exist_ok=True)
    # eval every ~200k total env-steps (eval_freq is per-env).
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=str(models_dir),
        eval_freq=max(1, 200_000 // n_envs),
        n_eval_episodes=1,
        deterministic=True,
        render=False,
    )

    model = PPO(
        "MultiInputPolicy",
        env,
        verbose=1,
        seed=42,
        # gamma raised from the 0.99 default (~1-day horizon) so battery
        # arbitrage over the day is valued. Drop to 0.997 if value loss is
        # unstable; try 0.999 if intraday-arbitrage credit is still too weak.
        gamma=0.998,
        gae_lambda=0.95,
        n_steps=2048,
        batch_size=2048,
        n_epochs=10,
        learning_rate=_linear_schedule(3e-4),
        ent_coef=0.01,
        clip_range=0.2,
        vf_coef=0.5,
        max_grad_norm=0.5,
        policy_kwargs=dict(net_arch=dict(pi=[256, 256], vf=[256, 256])),
    )

    logger_callback = EpisodeRewardLogger()
    model.learn(
        total_timesteps=total_timesteps, callback=[eval_callback, logger_callback]
    )

    # Persist to canonical paths so benchmark/dashboard/tests pick up the model.
    # Prefer EvalCallback's best checkpoint; fall back to the final policy.
    best_model = models_dir / "best_model.zip"
    if best_model.exists():
        shutil.copyfile(best_model, str(model_path) + ".zip")
        model = PPO.load(str(model_path))
    else:
        model.save(str(model_path))
    env.save(str(model_path) + "_vecnormalize.pkl")
    env.close()
    eval_env.close()
    return model


def _set_actor_trainable(policy, trainable: bool) -> None:
    """Freeze/unfreeze the actor (policy) branch of an ActorCriticPolicy.

    The critic branch is everything whose parameter name contains ``value_net``
    (``mlp_extractor.value_net.*`` and the ``value_net`` head); the actor is the
    rest (``mlp_extractor.policy_net``, ``action_net``, ``log_std``). Freezing
    the actor makes a PPO update train the critic only: with the actor fixed the
    policy ratio stays 1 and the policy/entropy losses have zero gradient.
    """
    for name, param in policy.named_parameters():
        if "value_net" not in name:
            param.requires_grad_(trainable)


class CriticWarmupCallback(BaseCallback):
    """Freeze the actor for the first ``warmup_steps``, then unfreeze.

    BC only trained the *policy* network (action MSE); the value net is random.
    Fine-tuning straight away feeds PPO garbage advantages, which drift the
    policy out of BC's arbitrage basin and back into the "never charge" local
    optimum. Warming the critic on BC-policy rollouts first makes the advantages
    point *toward* the arbitrage BC already does before the actor can move.
    """

    def __init__(self, warmup_steps: int, verbose: int = 1):
        super().__init__(verbose)
        self.warmup_steps = warmup_steps
        self._unfrozen = False

    def _on_training_start(self) -> None:
        _set_actor_trainable(self.model.policy, False)
        if self.verbose:
            print(
                f"[warmup] actor frozen for first {self.warmup_steps} steps", flush=True
            )

    def _on_step(self) -> bool:
        if not self._unfrozen and self.num_timesteps >= self.warmup_steps:
            _set_actor_trainable(self.model.policy, True)
            self._unfrozen = True
            if self.verbose:
                print(
                    f"[warmup] actor unfrozen at {self.num_timesteps} steps", flush=True
                )
        return True


class BillEvalCallback(BaseCallback):
    """Select the checkpoint with the lowest *bill*, not the highest reward.

    The training reward nets out shadow costs (unmet/shed/cycle penalties), so a
    lower-reward policy can still have a lower bill and vice-versa — exactly how
    the failed naive fine-tune "improved reward" while its bill got worse. This
    evaluates the true objective: it periodically saves the live model, benchmarks
    it (oracle mode, fast, no SARIMAX) against MPC on a few held-out seeds, and
    keeps the best-by-mean-bill checkpoint. ``bill_floor`` is seeded with BC's
    bill and BC is copied to ``out_path`` up front, so the fine-tune can never
    ship worse than BC.
    """

    def __init__(
        self,
        out_path: str | Path,
        eval_seeds,
        eval_freq: int,
        bill_floor: float,
        verbose: int = 1,
    ):
        super().__init__(verbose)
        self.out_path = str(out_path)
        self.eval_seeds = list(eval_seeds)
        self.eval_freq = eval_freq
        self.best_bill = bill_floor
        self._last_eval = 0
        self._mpc_bills: dict[int, float] = {}  # cached per seed (MPC is fixed)

    def _eval_bill(self) -> float:
        # Import here to avoid any import-time cost / cycles at module load.
        from shriteq.eval.benchmark import _run_ppo, _run_mpc, _scenario

        # Save the live policy + current normalization to a temp artifact so
        # RLPolicy (training=False) sees the same stats the training env uses.
        tmp = str(Path(self.out_path).with_name("_ft_tmp"))
        self.model.save(tmp)
        self.training_env.save(tmp + "_vecnormalize.pkl")
        cfg = SiteConfig()  # default config: bill is reward-config-independent
        ratios = []
        bills = []
        for seed in self.eval_seeds:
            load, solar = _scenario(cfg, seed)
            if seed not in self._mpc_bills:  # solve MPC once per seed, then reuse
                self._mpc_bills[seed] = _run_mpc(cfg, load, solar)["total_bill"]
            ppo = _run_ppo(cfg, load, solar, model_path=tmp + ".zip")
            bills.append(ppo["total_bill"])
            ratios.append(ppo["total_bill"] / self._mpc_bills[seed])
        mean_bill = float(np.mean(bills))
        mean_ratio = float(np.mean(ratios))
        if self.verbose:
            print(
                f"[bill-eval] step={self.num_timesteps} mean_bill={mean_bill:.0f} "
                f"mean_ratio_vs_mpc={mean_ratio:.4f} best_bill={self.best_bill:.0f}",
                flush=True,
            )
        return mean_bill

    def _on_step(self) -> bool:
        if self.num_timesteps - self._last_eval >= self.eval_freq:
            self._last_eval = self.num_timesteps
            bill = self._eval_bill()
            if bill < self.best_bill:
                self.best_bill = bill
                self.model.save(self.out_path)
                self.training_env.save(self.out_path + "_vecnormalize.pkl")
                if self.verbose:
                    print(
                        f"[bill-eval] NEW BEST bill={bill:.0f} -> saved {self.out_path}",
                        flush=True,
                    )
        return True


def finetune(
    bc_path: str | Path = "models/ppo_gridedge_bc",
    out_path: str | Path = "models/ppo_gridedge_ft",
    total_timesteps: int = 1_500_000,
    warmup_steps: int = 300_000,
    learning_rate: float = 2e-5,
    target_kl: float = 0.02,
    init_std: float = 0.1,
    eval_seeds=(0, 3),
    eval_freq: int = 200_000,
) -> PPO:
    """Corrected PPO fine-tune from behavior-cloned weights.

    The naive version regressed: a cold critic + exploration drift dropped the
    policy back into the "never charge" optimum, and best-model selection on
    *reward* couldn't catch it because reward != bill. This version fixes all
    three failure modes:

    * **Critic warm-up** (``CriticWarmupCallback``) fits the value net on
      BC-policy rollouts with the actor frozen, so advantages are sane before
      the actor moves.
    * **Stay near BC**: constant low LR, ``ent_coef=0`` (no forced exploration),
      and ``target_kl`` early-stopping keep updates from leaving BC's basin.
    * **``cycle_penalty=0``**: the env otherwise charges 2x MPC's ``wear_cost``
      for battery throughput, penalizing the arbitrage that lowers the bill. The
      bill has no cycling cost and round-trip loss already discourages churn.
      The unmet/shed penalties are kept — they stop the policy from "lowering the
      bill" by shedding load (which the bill metric doesn't charge for).
    * **Best-by-bill selection** (``BillEvalCallback``) keeps the checkpoint that
      actually bills lowest, floored at BC so we never ship a regression.
    """
    reward_log = Path("outputs/ppo_training_rewards.csv")
    if reward_log.exists():
        reward_log.unlink()

    # Reward config aligned with the bill: no extra cycling penalty vs MPC.
    config = SiteConfig(cycle_penalty=0.0)
    train_env = DummyVecEnv([make_env(config)])
    train_env = VecNormalize.load(str(bc_path) + "_vecnormalize.pkl", train_env)
    train_env.training = True
    train_env.norm_reward = True

    model = PPO.load(str(bc_path), env=train_env)
    # Gentle constant LR so BC behavior is refined, not overwritten.
    model.learning_rate = learning_rate
    model.lr_schedule = lambda _progress_remaining: learning_rate
    model.ent_coef = 0.0
    model.target_kl = target_kl
    # Tighter trust region than the 0.2 default to stay close to BC per update.
    model.clip_range = lambda _progress_remaining: 0.1
    # BC only trained the action *mean* (MSE), leaving log_std at the default
    # ~0 (std ~= 1) -- huge noise on a [-1, 1] action space. PPO then rolls out
    # near-random actions around BC's mean and drifts out of the arbitrage basin
    # (this sank both the naive fine-tune and the first corrected attempt). Shrink
    # exploration so the policy refines BC locally instead of wandering.
    import torch as _torch

    with _torch.no_grad():
        model.policy.log_std.fill_(float(np.log(init_std)))

    out_path = str(out_path)
    models_dir = Path(out_path).parent
    models_dir.mkdir(parents=True, exist_ok=True)

    # Seed the bill floor with BC and copy BC to out_path so a fine-tune that
    # never beats BC still leaves out_path == BC (safe to promote).
    bc_bill = _bc_bill_floor(bc_path, eval_seeds)
    shutil.copyfile(str(bc_path) + ".zip", out_path + ".zip")
    shutil.copyfile(str(bc_path) + "_vecnormalize.pkl", out_path + "_vecnormalize.pkl")
    print(
        f"[finetune] BC bill floor (seeds {list(eval_seeds)}) = {bc_bill:.0f}",
        flush=True,
    )

    warmup_callback = CriticWarmupCallback(warmup_steps=warmup_steps)
    bill_callback = BillEvalCallback(
        out_path, eval_seeds, eval_freq, bill_floor=bc_bill
    )
    logger_callback = EpisodeRewardLogger()
    model.learn(
        total_timesteps=total_timesteps,
        callback=[warmup_callback, bill_callback, logger_callback],
        reset_num_timesteps=True,
    )

    # out_path holds the best-by-bill checkpoint (>= BC quality). Load & return.
    best = PPO.load(out_path)
    train_env.close()
    return best


def _bc_bill_floor(bc_path: str | Path, eval_seeds) -> float:
    """Mean bill of the BC model over ``eval_seeds`` (oracle mode)."""
    from shriteq.eval.benchmark import _run_ppo, _scenario

    cfg = SiteConfig()
    bills = []
    for seed in eval_seeds:
        load, solar = _scenario(cfg, seed)
        ppo = _run_ppo(cfg, load, solar, model_path=str(bc_path) + ".zip")
        bills.append(ppo["total_bill"])
    return float(np.mean(bills))


if __name__ == "__main__":
    train()
