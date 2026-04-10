import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- App Config ---
st.set_page_config(page_title="Inventory Model Audit", layout="wide")
st.title("📊 Inventory Simulation: Physical Stock vs. Pipeline")

# --- Sidebar ---
st.sidebar.header("Operational Parameters")
avg_demand = st.sidebar.number_input("Avg Daily Demand", value=50)
std_demand = st.sidebar.number_input("Std Dev Demand", value=10)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=5, min_value=1)
order_cost = st.sidebar.number_input("Ordering Cost ($/order)", value=100.0)
holding_cost = st.sidebar.number_input("Holding Cost ($/unit/year)", value=2.0)

st.sidebar.divider()
st.sidebar.header("Model Settings")
service_level = st.sidebar.select_slider("Service Level (%)", options=[80, 85, 90, 95, 98, 99], value=95)
sim_days = st.sidebar.slider("Simulation Duration (Days)", 30, 365, 90)
review_period = st.sidebar.slider("P-System Review Frequency (Days)", 1, 30, 7)

# --- Calculations ---
z_map = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.645, 98: 2.05, 99: 2.33}
z = z_map[service_level]

# 1. Continuous Review (Q, R)
annual_demand = avg_demand * 365
eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
ss_rop = z * std_demand * np.sqrt(lead_time)
rop = (avg_demand * lead_time) + ss_rop

# 2. Periodic Review (R, S)
ss_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + ss_p

# --- Metrics Row ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("EOQ (Order Size)", f"{int(eoq)}")
m2.metric("Reorder Point (ROP)", f"{int(rop)}")
m3.metric("Target Level (S)", f"{int(target_level)}")
m4.metric("Safety Stock (P)", f"{int(ss_p)}")

# --- Simulation Engine ---
def run_master_sim():
    days = np.arange(sim_days)
    daily_demand = np.maximum(0, np.random.normal(avg_demand, std_demand, sim_days))
    
    # Storage for ROP
    inv_rop = np.zeros(sim_days); inv_rop[0] = eoq + ss_rop
    pending_rop = [] # (arrival_day, qty)
    triggers_rop = [] # (day, level)

    # Storage for P-System
    inv_p = np.zeros(sim_days); inv_p[0] = target_level
    pending_p = [] # (arrival_day, qty)
    triggers_p = [] # (day, level)

    for t in range(1, sim_days):
        # 1. Arrivals
        arr_rop = sum(q for d, q in pending_rop if d == t)
        arr_p = sum(q for d, q in pending_p if d == t)
        
        # 2. Update Physical Stock
        inv_rop[t] = max(0, inv_rop[t-1] - daily_demand[t] + arr_rop)
        inv_p[t] = max(0, inv_p[t-1] - daily_demand[t] + arr_p)
        
        # 3. Continuous Logic
        pos_rop = inv_rop[t] + sum(q for d, q in pending_rop if d > t)
        if pos_rop <= rop:
            pending_rop.append((t + lead_time, eoq))
            triggers_rop.append((t, inv_rop[t]))
            
        # 4. Periodic Logic
        if t % review_period == 0:
            pos_p = inv_p[t] + sum(q for d, q in pending_p if d > t)
            order_qty = max(0, target_level - pos_p)
            if order_qty > 0:
                pending_p.append((t + lead_time, order_qty))
                triggers_p.append((t, inv_p[t]))
                
    return days, inv_rop, inv_p, daily_demand, triggers_rop, triggers_p, pending_rop, pending_p

days, inv_rop, inv_p, demands, tri_rop, tri_p, pend_rop, pend_p = run_master_sim()

# --- Graph ---
fig = go.Figure()
fig.add_trace(go.Scatter(x=days, y=inv_rop, name="Continuous Stock", line=dict(color='#636EFA')))
fig.add_trace(go.Scatter(x=days, y=inv_p, name="Periodic Stock", line=dict(color='#00CC96')))

if tri_rop:
    rx, ry = zip(*tri_rop); fig.add_trace(go.Scatter(x=rx, y=ry, mode='markers', name='ROP Trigger', marker=dict(symbol='diamond', color='white')))
if tri_p:
    px, py = zip(*tri_p); fig.add_trace(go.Scatter(x=px, y=py, mode='markers', name='P-Review', marker=dict(symbol='circle', color='yellow')))

fig.add_hline(y=target_level, line_dash="dash", line_color="orange", annotation_text="Target S")
fig.add_hline(y=rop, line_dash="dot", line_color="red", annotation_text="ROP")

fig.update_layout(template="plotly_dark", height=500, title="Inventory Level Simulation", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# --- Audit Tables ---
st.subheader("📋 Detailed Audit Logs")
tab1, tab2 = st.tabs(["Continuous (ROP) Audit", "Periodic (P-System) Audit"])

with tab1:
    audit_rop = pd.DataFrame({
        "Day": days,
        "Physical Stock": inv_rop.astype(int),
        "On Order (Pipeline)": [sum(q for d, q in pend_rop if d > t and d <= t + lead_time) for t in days]
    })
    audit_rop["Inventory Position"] = audit_rop["Physical Stock"] + audit_rop["On Order (Pipeline)"]
    st.dataframe(audit_rop.set_index("Day"), use_container_width=True)

with tab2:
    audit_p = pd.DataFrame({
        "Day": days,
        "Physical Stock": inv_p.astype(int),
        "On Order (Pipeline)": [sum(q for d, q in pend_p if d > t and d <= t + lead_time) for t in days]
    })
    audit_p["Inventory Position"] = audit_p["Physical Stock"] + audit_p["On Order (Pipeline)"]
    st.dataframe(audit_p.set_index("Day"), use_container_width=True)
