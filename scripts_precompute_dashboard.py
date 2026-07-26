"""Precompute the dashboard benchmark cache.

Runs the seeded 30-day MPC/PPO benchmark once and writes the result under
``outputs/dashboard/`` so the Streamlit dashboard starts instantly instead of
recomputing on every page load. Re-run this whenever the deployed model
(``models/ppo_gridedge.zip``) changes.

    uv run python scripts_precompute_dashboard.py
"""

from shriteq.config import SiteConfig
from shriteq.eval.dashboard_cache import CACHE_DIR, build_cache


def main() -> None:
    bundle = build_cache(SiteConfig(), seed=42)
    mpc_bill = bundle["metrics"]["mpc"]["total_bill"]
    ppo_bill = bundle["metrics"]["ppo"]["total_bill"]
    savings_pct = (1 - ppo_bill / mpc_bill) * 100 if mpc_bill else 0.0
    print(f"Wrote dashboard cache to {CACHE_DIR}/")
    print(f"  MPC bill      = INR {mpc_bill:,.0f}")
    print(f"  Learned bill  = INR {ppo_bill:,.0f}")
    print(f"  Savings vs MPC = {savings_pct:.1f}%")


if __name__ == "__main__":
    main()
