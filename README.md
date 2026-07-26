<div align="center">

![freyr logo](./logo/Freyr_logo_vector.svg)

</div>

# Freyr

A simulation-first grid-edge energy load-balancing system for a single commercial site with rooftop solar, battery storage, flexible loads, time-of-use (ToU) pricing, and a monthly demand charge. It ships a transparent optimization baseline (MPC) and a learned dispatch policy (PPO, warm-started from the MPC via behavior cloning).

## Tech Stack

### AI Models

MPC (Model-Predictive Control). At each control instant it solves a convex optimization for the next 24 hours using the forecast, applies only the first step, then re-solves after the horizon rolls forward. Splitting battery power into separate nonnegative charge/discharge variables keeps the problem convex (QP), so OSQP solves it fast and globally. It is transparent — every rupee in the objective is inspectable — which makes it the trustworthy baseline. Its weakness is that it is only as good as its forecast and its hand-written objective.

PPO (Proximal Policy Optimization). A policy-gradient RL algorithm. It collects rollouts in the simulator, estimates each action's advantage with GAE, and takes a clipped gradient step (bounded by a KL trust region) so updates never move the policy too far at once. Here gamma=0.998 is essential: the effective horizon must span multiple days so the agent credits "charge cheap now" against "discharge expensive later" — the core arbitrage. PPO's promise is a fast, forecast-free reactive policy at inference time; its risk is local optima.

BC (Behavior Cloning). Supervised imitation. We roll the oracle MPC to generate expert (obs, action) pairs, then train the PPO network by minimizing MSE between its predicted action mean and MPC's action. This seeds PPO near MPC-quality arbitrage instead of a cold start. (Note: only the action mean is cloned; since RLPolicy predicts deterministic=True, the untrained log-std is irrelevant at evaluation.)

Supporting techniques. SARIMAX with calendar exogenous features for load forecasting; clear-sky irradiance + AR(1) cloud process for synthetic solar; a convex running-maximum encoding of the monthly peak so early spikes can't dodge the demand charge; potential-based reward shaping (Ng et al.) available but off by default because a potential difference is provably policy-invariant (keeps the reported bill honest).

#### UI

1. Live Web Dashboard: An interactive web dashboard built using [plotly](https://github.com/plotly/plotly.py) and [streamlit](https://streamlit.io/)
2. Handheld TUI Module:
   a. Hardware: Raspberry Pi Zero W with a 3.5" display in a 3d printed housing
   b. Software: A Terminal User Interface built with Ratatui in Rust.
