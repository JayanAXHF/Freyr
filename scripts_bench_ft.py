"""Benchmark the fine-tuned PPO (ppo_gridedge_ft) against MPC across seeds."""

from shriteq.config import SiteConfig
from shriteq.eval.benchmark import run_benchmark

MODEL = "models/ppo_gridedge_ft.zip"
SEEDS = [0, 1, 2, 3, 7]

cfg = SiteConfig()
mpc_bills, ft_bills, ratios = [], [], []

print(f"{'seed':>4} {'mpc_bill':>10} {'ft_bill':>10} {'ratio':>7} "
      f"{'mpc_energy':>10} {'ft_energy':>10} {'ft_ssc':>7} {'ft_shed':>8} {'ft_peak':>8}",
      flush=True)
for s in SEEDS:
    r = run_benchmark(cfg, seed=s, model_path=MODEL)
    mpc, ppo = r["mpc"], r["ppo"]
    ratio = ppo["total_bill"] / mpc["total_bill"]
    mpc_bills.append(mpc["total_bill"])
    ft_bills.append(ppo["total_bill"])
    ratios.append(ratio)
    print(f"{s:>4} {mpc['total_bill']:>10.0f} {ppo['total_bill']:>10.0f} {ratio:>7.3f} "
          f"{mpc['total_energy_cost']:>10.0f} {ppo['total_energy_cost']:>10.0f} "
          f"{ppo['solar_self_consumption']:>7.3f} {ppo['shed_load_kwh']:>8.1f} "
          f"{ppo['peak_kva']:>8.2f}",
          flush=True)

mean_mpc = sum(mpc_bills) / len(mpc_bills)
mean_ft = sum(ft_bills) / len(ft_bills)
mean_ratio_of_ratios = sum(ratios) / len(ratios)
agg_ratio = mean_ft / mean_mpc

print("=" * 60, flush=True)
print(f"mean mpc_bill = {mean_mpc:.0f}", flush=True)
print(f"mean ft_bill  = {mean_ft:.0f}", flush=True)
print(f"mean per-seed ratio = {mean_ratio_of_ratios:.4f}", flush=True)
print(f"aggregate ratio (mean_ft/mean_mpc) = {agg_ratio:.4f}", flush=True)
verdict = "PASS <=0.90" if agg_ratio <= 0.90 else ("BEATS MPC" if agg_ratio < 1.0 else "LOSES to MPC")
print(f"VERDICT: {verdict}  (savings vs MPC = {(1-agg_ratio)*100:.1f}%)", flush=True)
print("BENCH_DONE", flush=True)
