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
# For P-System, safety stock covers Lead Time + Review Period
ss_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + ss_p

# --- Display Key Metrics ---
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("EOQ (Fixed Q)", f"{int(eoq)}")
with m2:
    st.metric("Reorder Point (ROP)", f"{int(rop)}")
with m3:
    st.metric("P-System Target (S)", f"{int(target_level)}")
with m4:
    st.metric("Safety Stock (P)", f"{int(ss_p)}")

# --- Simulation Engine ---
def run_simulation():
    days = np.arange(sim_days)
    # Generate demand for all days
    daily_demand_arr = np.maximum(0, np.random.normal(avg_demand, std_demand, sim_days))
    
    # ROP Simulation State
    inv_rop = np.zeros(sim_days)
    inv_rop[0] = eoq + ss_rop
    pending_orders_rop = [] 
    order_triggers_rop = []

    # Periodic Simulation State
    inv_p = np.zeros(sim_days)
    inv_p[0] = target_level
    pending_orders_p = []
    order_triggers_p = []

    for t in range(1, sim_days):
        # 1. Process arrivals first
        rop_arrival = sum(qty for arrival_t, qty in pending_orders_rop if arrival_t == t)
        p_arrival = sum(qty for arrival_t, qty in pending_orders_p if arrival_t == t)
        
        # 2. Update physical inventory after demand
        inv_rop[t] = max(0, inv_rop[t-1] - daily_demand_arr[t] + rop_arrival)
        inv_p[t] = max(0, inv_p[t-1] - daily_demand_arr[t] + p_arrival)
        
        # 3. Continuous Review (ROP)
        on_hand_on_order_rop = inv_rop[t] + sum(qty for arrival_t, qty in pending_orders_rop if arrival_t > t)
        if on_hand_on_order_rop <= rop:
            pending_orders_rop.append((t + lead_time, eoq))
            order_triggers_rop.append((t, inv_rop[t]))
            
        # 4. Periodic Review (P-System)
        if t % review_period == 0:
            on_hand_on_order_p = inv_p[t] + sum(qty for arrival_t, qty in pending_orders_p if arrival_t > t)
            order_qty = target_level - on_hand_on_order_p
            if order_qty > 0:
                pending_orders_p.append((t + lead_time, order_qty))
                order_triggers_p.append((t, inv_p[t]))
                
    return days, inv_rop, inv_p, daily_demand_arr, order_triggers_rop, order_triggers_p

# Execute Simulation
days, inv_rop, inv_p, daily_demand_arr, triggers_rop, triggers_p = run_simulation()

# --- Visualization ---
fig = go.Figure()

# Plot Lines
fig.add_trace(go.Scatter(x=days, y=inv_rop, name="Continuous (ROP)", line=dict(color='#636EFA', width=2)))
fig.add_trace(go.Scatter(x=days, y=inv_p, name="Periodic (P-System)", line=dict(color='#00CC96', width=2)))

# Trigger Markers
if triggers_rop:
    tx_r, ty_r = zip(*triggers_rop)
    fig.add_trace(go.Scatter(x=tx_r, y=ty_r, mode='markers', name='ROP Trigger', 
                             marker=dict(color='blue', size=8, symbol='diamond')))
if triggers_p:
    tx_p, ty_p = zip(*triggers_p)
    fig.add_trace(go.Scatter(x=tx_p, y=ty_p, mode='markers', name='Review Point', 
                             marker=dict(color='green', size=8, symbol='circle')))

# Horizontal Target Lines
fig.add_hline(y=rop, line_dash="dot", line_color="rgba(255,0,0,0.5)", annotation_text="ROP")
fig.add_hline(y=target_level, line_dash="dash", line_color="rgba(255,165,0,0.5)", annotation_text="Target S")

fig.update_layout(
    title="Inventory Level Simulation",
    xaxis_title="Day", yaxis_title="Units",
    template="plotly_dark", height=600,
    hovermode="x unified"
)
st.plotly_chart(fig, use_container_width=True)

# --- Summary Statistics ---
st.subheader("Results Table")
col_stats, col_table = st.columns([1, 2])

with col_stats:
    stats_df = pd.DataFrame({
        "Metric": ["Stockout Days", "Total Orders", "Avg Inventory"],
        "Continuous": [(inv_rop <= 0).sum(), len(triggers_rop), int(inv_rop.mean())],
        "Periodic": [(inv_p <= 0).sum(), len(triggers_p), int(inv_p.mean())]
    })
    st.table(stats_df)

with col_table:
    # Fix: Correctly using daily_demand_arr here
    log_df = pd.DataFrame({
        "Day": days,
        "Demand": daily_demand_arr.astype(int),
        "Stock (ROP)": inv_rop.astype(int),
        "Stock (P-System)": inv_p.astype(int)
    }).set_index("Day")
    st.dataframe(log_df, height=300, use_container_width=True)
