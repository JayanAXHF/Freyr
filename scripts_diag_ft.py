"""Fast oracle-mode diagnostic: BC vs FT vs MPC on one seed + arbitrage trace."""

import numpy as np
import pandas as pd

from shriteq.config import SiteConfig
from shriteq.eval.benchmark import _scenario, _run_mpc, _run_ppo

cfg = SiteConfig()
SEED = 0
load, solar = _scenario(cfg, SEED)

# Oracle mode (forecast_load=None -> uses actual load; no SARIMAX fit = fast).
mpc = _run_mpc(cfg, load, solar)
print(f"MPC   bill={mpc['total_bill']:.0f} energy={mpc['total_energy_cost']:.0f} "
      f"ssc={mpc['solar_self_consumption']:.3f} peak={mpc['peak_kva']:.2f}", flush=True)

for tag, path in [("BC", "models/ppo_gridedge_bc.zip"), ("FT", "models/ppo_gridedge_ft.zip")]:
    metrics, rows = _run_ppo(cfg, load, solar, model_path=path, return_trace=True)
    df = pd.DataFrame(rows)
    df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
    # net battery: charge positive. site rows expose battery via grid? use charge/discharge if present.
    bcol = "battery_kw" if "battery_kw" in df else None
    # Reconstruct net charge from soc delta if battery_kw absent.
    price = df["tod_price_inr_per_kwh"]
    if bcol is None and "soc" in df:
        net = df["soc"].diff().fillna(0.0)  # proxy: soc rising = charging
    elif bcol is not None:
        net = -df[bcol]  # convention: battery_kw>0 discharge, so charge = -battery_kw
    else:
        net = pd.Series(np.zeros(len(df)))
    corr = float(np.corrcoef(net, price)[0, 1]) if net.std() > 0 else float("nan")
    cheap = net[df["hour"] < 6].clip(lower=0).sum()
    peak = (-net[(df["hour"] >= 18) & (df["hour"] < 22)]).clip(lower=0).sum()
    ratio = metrics["total_bill"] / mpc["total_bill"]
    print(f"{tag}    bill={metrics['total_bill']:.0f} energy={metrics['total_energy_cost']:.0f} "
          f"ssc={metrics['solar_self_consumption']:.3f} peak={metrics['peak_kva']:.2f} "
          f"ratio={ratio:.3f} | corr(net_charge,price)={corr:.3f} "
          f"cheap_charge~={cheap:.1f} peak_discharge~={peak:.1f} (soc-proxy units)",
          flush=True)

print("DIAG_DONE", flush=True)
