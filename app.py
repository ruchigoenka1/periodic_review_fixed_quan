import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- App Config ---
st.set_page_config(page_title="Inventory Strategy Simulator", layout="wide")
st.title("📦 Inventory Model Comparison: Continuous vs. Periodic")

# --- Sidebar Parameters ---
st.sidebar.header("Operational Inputs")
avg_demand = st.sidebar.number_input("Average Daily Demand", value=50)
std_demand = st.sidebar.number_input("Demand Std Dev (Volatility)", value=10)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=5, min_value=1)
order_cost = st.sidebar.number_input("Ordering Cost ($/Order)", value=100.0)
holding_cost = st.sidebar.number_input("Annual Holding Cost ($/Unit)", value=2.0)

st.sidebar.divider()
st.sidebar.header("Model Controls")
service_level = st.sidebar.select_slider("Service Level (%)", options=[80, 85, 90, 95, 98, 99], value=95)
sim_days = st.sidebar.slider("Simulation Horizon (Days)", 30, 365, 90)
review_period = st.sidebar.slider("P-System Review Frequency (Days)", 1, 30, 7)

# --- Math & Logic ---
z_map = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.645, 98: 2.05, 99: 2.33}
z = z_map[service_level]

# 1. Continuous Review (Q, R)
annual_demand = avg_demand * 365
eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
ss_rop = z * std_demand * np.sqrt(lead_time)
rop = (avg_demand * lead_time) + ss_rop

# 2. Periodic Review (R, S)
# S must cover Lead Time + Review Period
ss_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + ss_p

# --- Metrics Row ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("EOQ (Fixed Q)", f"{int(eoq)}")
m2.metric("Reorder Point (ROP)", f"{int(rop)}")
m3.metric("P-System Target (S)", f"{int(target_level)}")
m4.metric("Safety Stock (P-System)", f"{int(ss_p)}")

# --- Simulation Engine ---
def run_dual_simulation():
    days = np.arange(sim_days)
    daily_demand = np.maximum(0, np.random.normal(avg_demand, std_demand, sim_days))
    
    # Continuous State
    inv_rop = np.zeros(sim_days); inv_rop[0] = eoq + ss_rop
    pending_rop = [] # (arrival_day, qty)
    triggers_rop = []

    # Periodic State
    inv_p = np.zeros(sim_days); inv_p[0] = target_level
    pending_p = [] # (arrival_day, qty)
    triggers_p = []

    for t in range(1, sim_days):
        # Handle Arrivals
        arr_rop = sum(q for d, q in pending_rop if d == t)
        arr_p = sum(q for d, q in pending_p if d == t)
        
        # Update Physical Stock
        inv_rop[t] = max(0, inv_rop[t-1] - daily_demand[t] + arr_rop)
        inv_p[t] = max(0, inv_p[t-1] - daily_demand[t] + arr_p)
        
        # Continuous Logic (Check Position)
        pos_rop = inv_rop[t] + sum(q for d, q in pending_rop if d > t)
        if pos_rop <= rop:
            pending_rop.append((t + lead_time, eoq))
            triggers_rop.append((t, inv_rop[t]))
            
        # Periodic Logic (Check Position every T days)
        if t % review_period == 0:
            pos_p = inv_p[t] + sum(q for d, q in pending_p if d > t)
            order_qty = max(0, target_level - pos_p)
            if order_qty > 0:
                pending_p.append((t + lead_time, order_qty))
                triggers_p.append((t, inv_p[t]))
                
    return days, inv_rop, inv_p, daily_demand, triggers_rop, triggers_p

days, inv_rop, inv_p, demand_arr, tri_rop, tri_p = run_dual_simulation()

# --- Visualization ---
fig = go.Figure()

# Lines
fig.add_trace(go.Scatter(x=days, y=inv_rop, name="Continuous (ROP)", line=dict(color='#636EFA', width=2.5)))
fig.add_trace(go.Scatter(x=days, y=inv_p, name="Periodic (P-System)", line=dict(color='#00CC96', width=2.5)))

# Markers
if tri_rop:
    tx_r, ty_r = zip(*tri_rop)
    fig.add_trace(go.Scatter(x=tx_r, y=ty_r, mode='markers', name='ROP Trigger', marker=dict(color='white', symbol='diamond', size=8)))
if tri_p:
    tx_p, ty_p = zip(*tri_p)
    fig.add_trace(go.Scatter(x=tx_p, y=ty_p, mode='markers', name='P-Review', marker=dict(color='yellow', symbol='circle', size=8)))

# Thresholds
fig.add_hline(y=rop, line_dash="dot", line_color="red", annotation_text="ROP")
fig.add_hline(y=target_level, line_dash="dash", line_color="orange", annotation_text="Target S")

fig.update_layout(
    template="plotly_dark", height=600,
    xaxis_title="Simulation Day", yaxis_title="Units On Hand",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig, use_container_width=True)

# --- Data & Summary ---
col_a, col_b = st.columns([1, 2])

with col_a:
    st.subheader("Performance Summary")
    summary = pd.DataFrame({
        "Metric": ["Avg Inventory", "Stockout Days", "Total Orders Placed", "Min Stock Level"],
        "Continuous": [int(inv_rop.mean()), (inv_rop <= 0).sum(), len(tri_rop), int(inv_rop.min())],
        "Periodic": [int(inv_p.mean()), (inv_p <= 0).sum(), len(tri_p), int(inv_p.min())]
    })
    st.table(summary)

with col_b:
    st.subheader("Daily Transaction Log")
    log_df = pd.DataFrame({
        "Day": days,
        "Demand": demand_arr.astype(int),
        "ROP Stock": inv_rop.astype(int),
        "P-System Stock": inv_p.astype(int)
    }).set_index("Day")
    st.dataframe(log_df, height=300, use_container_width=True)
