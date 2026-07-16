"""Streamlit dashboard for GridEdge dispatch evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shriteq.config import SiteConfig
from shriteq.contracts import ForecastFrame, SiteState
from shriteq.control.mpc import MPCController
from shriteq.eval.benchmark import run_benchmark
from shriteq.sim.load_profiles import generate_load_series
from shriteq.forecast.solar_synth import generate as generate_solar


st.set_page_config(page_title="Shriteq GridEdge", layout="wide")
config = SiteConfig()


@st.cache_data
def dashboard_data():
    load = generate_load_series(config, "2026-01-05", 14)
    solar = generate_solar(config, "2026-01-05", 14)
    frames = [
        ForecastFrame(timestamp=load.index[i], load_mean_kw=float(load.iloc[i]), load_p10_kw=float(load.iloc[i] * .9), load_p90_kw=float(load.iloc[i] * 1.1), solar_mean_kw=float(solar.iloc[i]), solar_p10_kw=float(solar.iloc[i] * .9), solar_p90_kw=float(solar.iloc[i] * 1.1), price_inr_per_kwh=8.0, demand_rate_inr_per_kva=float(config.demand_charge_inr_per_kva_month), tariff_block_id=0)
        for i in range(96)
    ]
    mpc = MPCController(config)
    plan = mpc.solve(SiteState(load.index[0], .5, float(load.iloc[0]), float(solar.iloc[0]), 0.0, 0, 60), frames)
    benchmark = run_benchmark(config, 42)
    return load, solar, plan, benchmark


st.title("Shriteq GridEdge")
load, solar, plan, benchmark = dashboard_data()

st.header("Now")
now = st.columns(5)
now[0].metric("Current load", f"{load.iloc[0]:.2f} kW")
now[1].metric("Solar", f"{solar.iloc[0]:.2f} kW")
now[2].metric("SOC", "50.0%")
now[3].metric("Tariff block", "0")
now[4].metric("Billing peak", "0.00 kVA")

st.header("Next 24h")
next_day = load.index[:96]
figure = go.Figure()
figure.add_trace(go.Scatter(x=next_day, y=load.iloc[:96], name="Load"))
figure.add_trace(go.Scatter(x=next_day, y=solar.iloc[:96], name="Solar"))
figure.add_trace(go.Scatter(x=next_day, y=np.full(96, plan.grid_import_kw), name="Planned grid import"))
figure.update_layout(xaxis_title="Time", yaxis_title="Power (kW)", height=420)
st.plotly_chart(figure, use_container_width=True)

st.header("Benchmark")
benchmark_frame = pd.DataFrame(benchmark).T
benchmark_frame["savings_pct"] = (1 - benchmark_frame["total_bill"] / benchmark_frame.loc["mpc", "total_bill"]) * 100
st.dataframe(benchmark_frame[["total_energy_cost", "demand_charge_incurred", "total_bill", "peak_kva", "unmet_load_kwh", "unmet_events", "solar_self_consumption", "savings_pct"]].style.format("{:.2f}"))
