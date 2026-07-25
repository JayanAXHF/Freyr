"""Generalization sweep: FT (obs-norm-corrected BC) vs BC vs MPC across seeds.

Seeds 0,3 were used for best-by-bill selection; 1,2,7 are held out.
"""

import numpy as np
from shriteq.config import SiteConfig
from shriteq.eval.benchmark import _scenario, _run_mpc, _run_ppo

cfg = SiteConfig()
SEEDS = [0, 1, 2, 3, 7]
SELECT = {0, 3}
BC = "models/ppo_gridedge_bc.zip"
FT = "models/ppo_gridedge_ft.zip"

print(f"{'seed':>4} {'held':>5} {'mpc':>8} {'bc':>8} {'ft':>8} "
      f"{'bc_r':>6} {'ft_r':>6} {'ft_ssc':>7} {'ft_peak':>8} {'ft_shed':>8}", flush=True)

bc_ratios, ft_ratios, held_ft_ratios = [], [], []
for s in SEEDS:
    load, solar = _scenario(cfg, s)
    mpc = _run_mpc(cfg, load, solar)
    bc = _run_ppo(cfg, load, solar, model_path=BC)
    ft = _run_ppo(cfg, load, solar, model_path=FT)
    bc_r = bc["total_bill"] / mpc["total_bill"]
    ft_r = ft["total_bill"] / mpc["total_bill"]
    bc_ratios.append(bc_r)
    ft_ratios.append(ft_r)
    held = "no" if s in SELECT else "YES"
    if s not in SELECT:
        held_ft_ratios.append(ft_r)
    print(f"{s:>4} {held:>5} {mpc['total_bill']:>8.0f} {bc['total_bill']:>8.0f} "
          f"{ft['total_bill']:>8.0f} {bc_r:>6.3f} {ft_r:>6.3f} "
          f"{ft['solar_self_consumption']:>7.3f} {ft['peak_kva']:>8.2f} "
          f"{ft['shed_load_kwh']:>8.1f}", flush=True)

print("=" * 70, flush=True)
print(f"BC mean ratio (all)      = {np.mean(bc_ratios):.4f}  ({(1-np.mean(bc_ratios))*100:.1f}% below MPC)", flush=True)
print(f"FT mean ratio (all)      = {np.mean(ft_ratios):.4f}  ({(1-np.mean(ft_ratios))*100:.1f}% below MPC)", flush=True)
print(f"FT mean ratio (held-out) = {np.mean(held_ft_ratios):.4f}  ({(1-np.mean(held_ft_ratios))*100:.1f}% below MPC)", flush=True)
ft_all = np.mean(ft_ratios)
verdict = "PASS >=10% below MPC" if ft_all <= 0.90 else ("BEATS MPC" if ft_all < 1.0 else "LOSES")
better_than_bc = "YES" if ft_all < np.mean(bc_ratios) else "NO"
print(f"VERDICT: {verdict}; FT better than BC: {better_than_bc}", flush=True)
print("BENCH2_DONE", flush=True)
