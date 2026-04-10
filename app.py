import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- App Config ---
st.set_page_config(page_title="Inventory Model Pro", layout="wide")
st.title("📊 Advanced Inventory Simulation")

# --- Sidebar Inputs ---
st.sidebar.header("Parameters")
avg_demand = st.sidebar.number_input("Avg Daily Demand", value=50)
std_demand = st.sidebar.number_input("Std Dev Demand", value=10)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=5, min_value=1)
holding_cost = st.sidebar.number_input("Holding Cost ($/unit/year)", value=2.0)
order_cost = st.sidebar.number_input("Ordering Cost ($/order)", value=100.0)
service_level = st.sidebar.select_slider("Service Level (%)", options=[80, 85, 90, 95, 98, 99], value=95)
sim_days = st.sidebar.slider("Simulation Duration (Days)", 30, 365, 90)

# Constants
z_map = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.645, 98: 2.05, 99: 2.33}
z = z_map[service_level]

# --- 1. CORE CALCULATIONS ---
annual_demand = avg_demand * 365
eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
ss_rop = z * std_demand * np.sqrt(lead_time)
rop = (avg_demand * lead_time) + ss_rop

review_period = st.sidebar.slider("Review Period (Days)", 1, 30, 7)
ss_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + ss_p

# --- Display Key Metrics ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("EOQ (Order Qty)", f"{int(eoq)}")
with m2:
    st.metric("Reorder Point (ROP)", f"{int(rop)}")
with m3:
    st.metric("P-System Target (S)", f"{int(target_level)}")
with m4:
    st.metric("Safety Stock (P)", f"{int(ss_p)}")

# --- Simulation Engine ---
def run_simulation():
    days = np.arange(sim_days)
    daily_demand = np.maximum(0, np.random.normal(avg_demand, std_demand, sim_days))
    
    inv_rop = np.zeros(sim_days)
    inv_rop[0] = eoq + ss_rop
    pending_orders_rop = [] 
    order_triggers_rop = [] # To store (day, level) for dots

    inv_p = np.zeros(sim_days)
    inv_p[0] = target_level
    pending_orders_p = []
    order_triggers_p = [] # To store (day, level) for dots

    for t in range(1, sim_days):
        rop_arrival = sum(qty for day, qty in pending_orders_rop if day == t)
        p_arrival = sum(qty for day, qty in pending_orders_p if day == t)
        
        inv_rop[t] = max(0, inv_rop[t-1] - daily_demand[t] + rop_arrival)
        inv_p[t] = max(0, inv_p[t-1] - daily_demand[t] + p_arrival)
        
        # Continuous Trigger
        on_order_rop = sum(qty for day, qty in pending_orders_rop if day > t)
        if (inv_rop[t] + on_order_rop) <= rop:
            pending_orders_rop.append((t + lead_time, eoq))
            order_triggers_rop.append((t, inv_rop[t]))
            
        # Periodic Trigger
        if t % review_period == 0:
            on_order_p = sum(qty for day, qty in pending_orders_p if day > t)
            needed = target_level - (inv_p[t] + on_order_p)
            if needed > 0:
                pending_orders_p.append((t + lead_time, needed))
                order_triggers_p.append((t, inv_p[t]))
                
    return days, inv_rop, inv_p, demands, order_triggers_rop, order_triggers_p

days, inv_rop, inv_p, demands, triggers_rop, triggers_p = run_simulation()

# --- Visualization ---
fig = go.Figure()

# Lines
fig.add_trace(go.Scatter(x=days, y=inv_rop, name="Continuous (ROP)", line=dict(color='#636EFA', width=2)))
fig.add_trace(go.Scatter(x=days, y=inv_p, name="Periodic (P-System)", line=dict(color='#00CC96', width=2)))

# Trigger Points (Markers)
if triggers_rop:
    tx_rop, ty_rop = zip(*triggers_rop)
    fig.add_trace(go.Scatter(x=tx_rop, y=ty_rop, mode='markers', name='ROP Order Placed', 
                             marker=dict(color='blue', size=10, symbol='diamond')))

if triggers_p:
    tx_p, ty_p = zip(*triggers_p)
    fig.add_trace(go.Scatter(x=tx_p, y=ty_p, mode='markers', name='P-System Review', 
                             marker=dict(color='green', size=10, symbol='circle')))

# ROP and Target Level Reference Lines
fig.add_hline(y=rop, line_dash="dot", line_color="red", annotation_text="ROP Level")
fig.add_hline(y=target_level, line_dash="dash", line_color="orange", annotation_text="P-System Target")

fig.update_layout(
    title="Inventory Simulation with Order Points",
    xaxis_title="Day",
    yaxis_title="Units on Hand",
    template="plotly_dark",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600
)
st.plotly_chart(fig, use_container_width=True)

# --- Summary Statistics ---
st.subheader("Model Performance Summary")
col_stats, col_table = st.columns([1, 2])

with col_stats:
    stats = pd.DataFrame({
        "Metric": ["Min Stock", "Stockout Days", "Total Orders", "Avg Inventory"],
        "Continuous": [int(inv_rop.min()), (inv_rop <= 0).sum(), len(triggers_rop), int(inv_rop.mean())],
        "Periodic": [int(inv_p.min()), (inv_p <= 0).sum(), len(triggers_p), int(inv_p.mean())]
    })
    st.table(stats)

with col_table:
    df_log = pd.DataFrame({
        "Day": days,
        "Demand": demands.astype(int),
        "Stock (ROP)": inv_rop.astype(int),
        "Stock (Periodic)": inv_p.astype(int)
    }).set_index("Day")
    st.dataframe(df_log, height=300, use_container_width=True)
