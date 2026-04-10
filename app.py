import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- App Config ---
st.set_page_config(page_title="Inventory Strategy Audit", layout="wide")

# --- Custom CSS for Zoom Toolbar Padding ---
st.markdown("""
    <style>
    section[data-testid="stSidebar"] > div {
        padding-left: 70px;
        padding-right: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Inventory Simulation: Financial & Operational Audit")

# --- 1. CAPTURE CONTROLS FIRST (Crucial for State Sync) ---
st.sidebar.header("Controls")
sim_days = st.sidebar.slider("Simulation Horizon (Days)", 30, 365, 90)
review_period = st.sidebar.slider("P-System Review Frequency (Days)", 1, 30, 7)

# Generate Button Logic
if st.sidebar.button("🔄 Generate New Demand Scenario"):
    st.session_state['demand_data'] = None
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Operational Parameters")
avg_demand = st.sidebar.number_input("Avg Daily Demand", value=50)
std_demand = st.sidebar.number_input("Demand Std Dev", value=10)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=5, min_value=1)
order_cost = st.sidebar.number_input("Ordering Cost ($/order)", value=100.0)
holding_cost_annual = st.sidebar.number_input("Holding Cost ($/unit/year)", value=2.0)
stockout_penalty = st.sidebar.number_input("Stockout Penalty ($/unit)", value=5.0)
service_level = st.sidebar.select_slider("Service Level (%)", options=[80, 85, 90, 95, 98, 99], value=95)

# --- 2. DEMAND STATE MANAGEMENT ---
# This checks if the existing data matches the current slider length
if 'demand_data' not in st.session_state or st.session_state['demand_data'] is None or len(st.session_state['demand_data']) != sim_days:
    st.session_state['demand_data'] = np.maximum(0, np.random.normal(avg_demand, std_demand, sim_days))

daily_demand_arr = st.session_state['demand_data']

# --- 3. MATH CALCULATIONS ---
z_map = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.645, 98: 2.05, 99: 2.33}
z = z_map[service_level]
holding_cost_daily = holding_cost_annual / 365

# ROP Calcs
annual_demand = avg_demand * 365
eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost_annual)
ss_rop = z * std_demand * np.sqrt(lead_time)
rop = (avg_demand * lead_time) + ss_rop

# P-System Calcs
ss_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + ss_p

# --- UI DISPLAY ---
m1, m2, m3, m4 = st.columns(4)
m1.metric("EOQ (Fixed Q)", f"{int(eoq)}")
m2.metric("Reorder Point (ROP)", f"{int(rop)}")
m3.metric("Target Level (S)", f"{int(target_level)}")
m4.metric("Safety Stock (P)", f"{int(ss_p)}")

# --- SIMULATION ENGINE ---
def run_simulation():
    days = np.arange(sim_days)
    inv_rop = np.zeros(sim_days); inv_rop[0] = eoq + ss_rop
    pos_rop_log = np.zeros(sim_days); pend_rop = []; tri_rop = []; so_units_rop = 0
    inv_p = np.zeros(sim_days); inv_p[0] = target_level
    pos_p_log = np.zeros(sim_days); pend_p = []; tri_p = []; so_units_p = 0

    for t in range(1, sim_days):
        arr_rop = sum(q for d, q in pend_rop if d == t)
        arr_p = sum(q for d, q in pend_p if d == t)
        pot_rop = inv_rop[t-1] + arr_rop
        pot_p = inv_p[t-1] + arr_p
        
        if pot_rop < daily_demand_arr[t]: so_units_rop += (daily_demand_arr[t] - pot_rop)
        if pot_p < daily_demand_arr[t]: so_units_p += (daily_demand_arr[t] - pot_p)

        inv_rop[t] = max(0, pot_rop - daily_demand_arr[t])
        inv_p[t] = max(0, pot_p - daily_demand_arr[t])
        
        # Position Logic
        pos_rop = inv_rop[t] + sum(q for d, q in pend_rop if d > t)
        pos_rop_log[t] = pos_rop
        if pos_rop <= rop:
            pend_rop.append((t + lead_time, eoq))
            tri_rop.append((t, inv_rop[t]))
            
        pos_p = inv_p[t] + sum(q for d, q in pend_p if d > t)
        if t % review_period == 0:
            order_qty = max(0, target_level - pos_p)
            if order_qty > 0:
                pend_p.append((t + lead_time, order_qty))
                tri_p.append((t, inv_p[t]))
                pos_p += order_qty
        pos_p_log[t] = pos_p
                
    return days, inv_rop, inv_p, tri_rop, tri_p, pend_rop, pend_p, so_units_rop, so_units_p, pos_rop_log, pos_p_log

days, inv_rop, inv_p, tri_rop, tri_p, p_rop, p_p, so_rop, so_p, pos_rop_l, pos_p_l = run_simulation()

# --- FINANCIALS ---
hold_rop = inv_rop.sum() * holding_cost_daily
ord_rop = len(tri_rop) * order_cost
stock_rop = so_rop * stockout_penalty
hold_p = inv_p.sum() * holding_cost_daily
ord_p = len(tri_p) * order_cost
stock_p = so_p * stockout_penalty

st.subheader("📊 Financial Performance")
c1, c2 = st.columns([1, 1.5])
with c1:
    summary = pd.DataFrame({
        "Cost Item": ["Holding", "Ordering", "Stockout", "Total"],
        "Continuous (ROP)": [f"${hold_rop:,.2f}", f"${ord_rop:,.2f}", f"${stock_rop:,.2f}", f"${(hold_rop+ord_rop+stock_rop):,.2f}"],
        "Periodic (P)": [f"${hold_p:,.2f}", f"${ord_p:,.2f}", f"${stock_p:,.2f}", f"${(hold_p+ord_p+stock_p):,.2f}"]
    })
    st.table(summary)
with c2:
    fig_bar = go.Figure(data=[
        go.Bar(name='Continuous', x=['Total Cost'], y=[hold_rop+ord_rop+stock_rop]),
        go.Bar(name='Periodic', x=['Total Cost'], y=[hold_p+ord_p+stock_p])
    ])
    fig_bar.update_layout(template="plotly_dark", height=300, barmode='group')
    st.plotly_chart(fig_bar, use_container_width=True)

# --- VISUALIZATION ---
st.subheader("📈 Inventory Levels: Physical vs. Position")
fig = go.Figure()
fig.add_trace(go.Scatter(x=days, y=inv_rop, name="Continuous (Physical)", line=dict(color='#636EFA', width=3)))
fig.add_trace(go.Scatter(x=days, y=inv_p, name="Periodic (Physical)", line=dict(color='#00CC96', width=3)))
fig.add_trace(go.Scatter(x=days, y=pos_rop_l, name="Continuous (Position)", line=dict(color='#636EFA', width=1, dash='dot')))
fig.add_trace(go.Scatter(x=days, y=pos_p_l, name="Periodic (Position)", line=dict(color='#00CC96', width=1, dash='dot')))

if tri_rop:
    rx, ry = zip(*tri_rop); fig.add_trace(go.Scatter(x=rx, y=ry, mode='markers', name='ROP Trigger', marker=dict(symbol='diamond', color='white', size=8)))
if tri_p:
    px, py = zip(*tri_p); fig.add_trace(go.Scatter(x=px, y=py, mode='markers', name='P-Review Point', marker=dict(symbol='circle', color='yellow', size=8)))

fig.add_hline(y=target_level, line_dash="dash", line_color="orange", opacity=0.4, annotation_text="Target S")
fig.add_hline(y=rop, line_dash="dot", line_color="red", opacity=0.4, annotation_text="ROP")
fig.update_layout(template="plotly_dark", height=600, hovermode="x unified", legend=dict(orientation="h", y=1.08))
st.plotly_chart(fig, use_container_width=True)

# --- AUDIT LOGS ---
st.subheader("📋 Audit Logs")
t1, t2 = st.tabs(["Continuous Audit", "Periodic Audit"])
with t1:
    audit_rop = pd.DataFrame({"Day": days, "Demand": daily_demand_arr.astype(int), "Physical": inv_rop.astype(int), "Position": pos_rop_l.astype(int)})
    st.dataframe(audit_rop.set_index("Day"), use_container_width=True)
with t2:
    audit_p = pd.DataFrame({"Day": days, "Demand": daily_demand_arr.astype(int), "Physical": inv_p.astype(int), "Position": pos_p_l.astype(int)})
    st.dataframe(audit_p.set_index("Day"), use_container_width=True)
