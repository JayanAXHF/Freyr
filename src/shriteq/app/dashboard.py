"""Streamlit dashboard for GridEdge dispatch evaluation.

Reads a precomputed benchmark cache (``outputs/dashboard/``) instead of running
the 30-day MPC/PPO benchmark on every page load, so startup is near-instant. Run
``uv run python scripts_precompute_dashboard.py`` to (re)generate the cache.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from shriteq.config import SiteConfig
from shriteq.eval.dashboard_cache import cache_is_stale, load_cache

st.set_page_config(page_title="Shriteq GridEdge", layout="wide")
config = SiteConfig()

# The deployed policy is stored under "ppo" in the benchmark but is a
# behavior-cloned + obs-norm-refit policy; surface it under its real name.
LEARNED = "learned"


def _theme_base() -> str:
    try:
        return st.get_option("theme.base") or "light"
    except Exception:  # pragma: no cover - defensive; option always exists
        return "light"


# Categorical palette (dataviz skill): controllers keep the same two hues in
# every comparison chart — MPC blue, learned orange — validated in both modes.
_LIGHT = {
    "mpc": "#2a78d6",
    "learned": "#eb6834",
    "load": "#2a78d6",
    "grid": "#e34948",
    "solar": "#eda100",
    "battery": "#1baf7a",
    "soc": "#4a3aa7",
    "energy": "#2a78d6",
    "demand": "#eb6834",
    "shade": "17, 17, 17",  # neutral ink for tariff bands on a light surface
}
_DARK = {
    "mpc": "#3987e5",
    "learned": "#d95926",
    "load": "#3987e5",
    "grid": "#e66767",
    "solar": "#c98500",
    "battery": "#199e70",
    "soc": "#9085e9",
    "energy": "#3987e5",
    "demand": "#d95926",
    "shade": "255, 255, 255",  # neutral ink for tariff bands on a dark surface
}
PALETTE = _DARK if _theme_base() == "dark" else _LIGHT


@st.cache_data
def dashboard_data():
    """Load the on-disk benchmark cache (cheap parquet/JSON reads)."""
    return load_cache()


bundle = dashboard_data()

st.title("Shriteq GridEdge")

if bundle is None:
    st.error(
        "No dashboard cache found under `outputs/dashboard/`. Generate it with:\n\n"
        "```\nuv run python scripts_precompute_dashboard.py\n```"
    )
    st.stop()

metrics = bundle["metrics"]
mpc_metrics = metrics["mpc"]
learned_metrics = metrics["ppo"]
traces = bundle["traces"]
series = bundle["series"]
meta = bundle["meta"]

mpc_bill = mpc_metrics["total_bill"]
learned_bill = learned_metrics["total_bill"]
savings_pct = (1 - learned_bill / mpc_bill) * 100 if mpc_bill else 0.0

# --- 1. Hero savings banner -------------------------------------------------
if cache_is_stale(meta):
    st.warning(
        "The deployed model is newer than this cache. Re-run "
        "`uv run python scripts_precompute_dashboard.py` to refresh the numbers."
    )

hero = st.columns([2, 1, 2])
hero[0].metric(
    "Learned policy — monthly bill",
    f"₹{learned_bill:,.0f}",
    delta=f"{-savings_pct:.1f}% vs MPC",
    delta_color="inverse",  # a lower bill is better → green down-arrow
)
hero[1].metric("MPC baseline", f"₹{mpc_bill:,.0f}")
hero[2].caption(
    f"Seed-{meta['seed']} 30-day forecast-driven run. The learned policy "
    "arbitrages the battery like MPC and bills below it while holding service "
    "quality. `savings_pct` is measured against MPC."
)

# --- 2. KPI comparison row --------------------------------------------------
st.subheader("MPC vs learned")


def _kpi(
    column, label, key, digits, prefix="", suffix="", lower_is_better=True, scale=1.0
):
    mpc_value = mpc_metrics[key] * scale
    learned_value = learned_metrics[key] * scale
    delta = learned_value - mpc_value
    # The numeric sign must lead the delta string: Streamlit misreads the sign
    # (and paints the arrow the wrong colour) when a prefix like "₹" comes first.
    sign = "-" if delta < 0 else ""
    column.metric(
        label,
        f"{prefix}{learned_value:,.{digits}f}{suffix}",
        delta=f"{sign}{prefix}{abs(delta):,.{digits}f}{suffix}",
        delta_color="inverse" if lower_is_better else "normal",
    )


kpi = st.columns(5)
_kpi(kpi[0], "Total bill", "total_bill", 0, prefix="₹")
_kpi(kpi[1], "Energy cost", "total_energy_cost", 0, prefix="₹")
_kpi(kpi[2], "Demand charge", "demand_charge_incurred", 0, prefix="₹")
_kpi(kpi[3], "Peak", "peak_kva", 1, suffix=" kVA")
_kpi(
    kpi[4],
    "Solar self-use",
    "solar_self_consumption",
    0,
    suffix="%",
    lower_is_better=False,
    scale=100,
)

# --- 3. Dispatch trace (the money chart) ------------------------------------
st.subheader("Daily dispatch")
st.caption(
    "Battery charges in the cheap ₹5 overnight block and discharges into the "
    "₹10 evening peak. Shading = tariff price (darker is pricier)."
)

traces = traces.copy()
traces["timestamp"] = pd.to_datetime(traces["timestamp"])
series = series.copy()
series.index = pd.to_datetime(series.index)

days = sorted({ts.date() for ts in traces["timestamp"]})
controls = st.columns([2, 2])
day = controls[0].selectbox(
    "Day", days, index=min(len(days) - 1, len(days) // 2), format_func=str
)
controller_label = controls[1].radio("Controller", [LEARNED, "mpc"], horizontal=True)
controller_key = "ppo" if controller_label == LEARNED else "mpc"

day_trace = traces[
    (traces["controller"] == controller_key) & (traces["timestamp"].dt.date == day)
].sort_values("timestamp")
day_series = series[series.index.date == day]

figure = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.72, 0.28],
    vertical_spacing=0.06,
)

# Top: power flows. Solar and battery are filled (readable as areas); load and
# grid import are lines that clear the 3:1 contrast floor for thin marks.
battery_net = day_trace["battery_discharge_kw"] - day_trace["battery_charge_kw"]

# Fixed y-ranges so the tariff bands (below) fill each panel exactly.
power_hi = (
    float(
        max(
            day_series["load"].max(),
            day_series["solar"].max(),
            day_trace["grid_import_kw"].max(),
            battery_net.max(),
        )
    )
    * 1.08
)
power_lo = min(0.0, float(battery_net.min())) * 1.15

# Tariff price shading, drawn as filled traces (Streamlit strips layout shapes
# from a templated figure, but always renders traces). Opacity scales with the
# block price so the eye reads darker = pricier. Match the axis timezone
# (Asia/Kolkata) so the bands align with the data.
prices = [block["price_inr_per_kwh"] for block in config.tariff_blocks]
low, high = min(prices), max(prices)
day_start = pd.Timestamp(day).tz_localize(config.tz)
for block in config.tariff_blocks:
    opacity = 0.05 + (block["price_inr_per_kwh"] - low) / (high - low or 1) * 0.25
    x0 = day_start + pd.Timedelta(hours=block["start_hour"])
    x1 = day_start + pd.Timedelta(hours=block["end_hour"])
    fill = f"rgba({PALETTE['shade']}, {opacity:.3f})"
    for panel, (lo, hi) in ((1, (power_lo, power_hi)), (2, (0, 100))):
        figure.add_trace(
            go.Scatter(
                x=[x0, x1, x1, x0],
                y=[lo, lo, hi, hi],
                fill="toself",
                fillcolor=fill,
                line_width=0,
                mode="lines",
                hoverinfo="skip",
                showlegend=False,
            ),
            row=panel,
            col=1,
        )
figure.add_trace(
    go.Scatter(
        x=day_series.index,
        y=day_series["solar"],
        name="Solar",
        mode="lines",
        line=dict(color=PALETTE["solar"], width=1.5),
        fill="tozeroy",
        fillcolor=f"rgba(237, 161, 0, 0.18)",
    ),
    row=1,
    col=1,
)
figure.add_trace(
    go.Scatter(
        x=day_trace["timestamp"],
        y=battery_net,
        name="Battery (+ discharge / − charge)",
        mode="lines",
        line=dict(color=PALETTE["battery"], width=1.5),
        fill="tozeroy",
        fillcolor=f"rgba(27, 175, 122, 0.18)",
    ),
    row=1,
    col=1,
)
figure.add_trace(
    go.Scatter(
        x=day_series.index,
        y=day_series["load"],
        name="Load",
        mode="lines",
        line=dict(color=PALETTE["load"], width=2),
    ),
    row=1,
    col=1,
)
figure.add_trace(
    go.Scatter(
        x=day_trace["timestamp"],
        y=day_trace["grid_import_kw"],
        name="Grid import",
        mode="lines",
        line=dict(color=PALETTE["grid"], width=2),
    ),
    row=1,
    col=1,
)

# Bottom: state of charge on its own axis (no dual-axis).
figure.add_trace(
    go.Scatter(
        x=day_trace["timestamp"],
        y=day_trace["soc"] * 100,
        name="SOC",
        mode="lines",
        line=dict(color=PALETTE["soc"], width=2),
    ),
    row=2,
    col=1,
)

figure.update_yaxes(title_text="Power (kW)", range=[power_lo, power_hi], row=1, col=1)
figure.update_yaxes(title_text="SOC (%)", range=[0, 100], row=2, col=1)
figure.update_xaxes(title_text="Time", row=2, col=1)
figure.update_layout(
    height=520,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(t=40, b=40, l=60, r=20),
)
# Let Streamlit theme the chrome (light/dark); trace colours stay explicit.
st.plotly_chart(figure, use_container_width=True)

# --- 4. Cost breakdown ------------------------------------------------------
st.subheader("Cost breakdown")
cost = go.Figure()
labels = ["MPC", "Learned"]
energy = [mpc_metrics["total_energy_cost"], learned_metrics["total_energy_cost"]]
demand = [
    mpc_metrics["demand_charge_incurred"],
    learned_metrics["demand_charge_incurred"],
]
cost.add_trace(
    go.Bar(x=labels, y=energy, name="Energy cost", marker_color=PALETTE["energy"])
)
cost.add_trace(
    go.Bar(x=labels, y=demand, name="Demand charge", marker_color=PALETTE["demand"])
)
cost.update_layout(
    barmode="stack",
    bargap=0.5,
    height=380,
    yaxis_title="Cost (₹)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(t=40, b=40, l=60, r=20),
)
st.plotly_chart(cost, use_container_width=True)

# --- 5. Detail table (full numbers drill-down) ------------------------------
st.subheader("Full metrics")
benchmark_frame = pd.DataFrame({"mpc": mpc_metrics, LEARNED: learned_metrics}).T
mpc_shed = benchmark_frame.loc["mpc", "shed_load_kwh"]
mpc_events = benchmark_frame.loc["mpc", "shed_events"]
benchmark_frame["savings_pct"] = np.where(
    True,
    (1 - benchmark_frame["total_bill"] / benchmark_frame.loc["mpc", "total_bill"])
    * 100,
    np.nan,
)
st.dataframe(
    benchmark_frame[
        [
            "total_energy_cost",
            "demand_charge_incurred",
            "total_bill",
            "peak_kva",
            "shed_load_kwh",
            "shed_events",
            "unmet_load_kwh",
            "unmet_events",
            "solar_self_consumption",
            "savings_pct",
        ]
    ].style.format(
        "{:.2f}",
        subset=pd.IndexSlice[:, benchmark_frame.columns != "service_quality_ok"],
    )
)
