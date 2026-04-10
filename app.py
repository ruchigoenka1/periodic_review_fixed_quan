import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- App Config ---
st.set_page_config(page_title="Inventory Model Comparator", layout="wide")
st.title("📦 Inventory Model Comparison: Continuous vs. Periodic")

# --- Sidebar Inputs ---
st.sidebar.header("Demand & Costs")
avg_demand = st.sidebar.number_input("Average Daily Demand", value=50)
std_demand = st.sidebar.number_input("Std Dev of Daily Demand", value=10)
lead_time = st.sidebar.number_input("Lead Time (Days)", value=5)
holding_cost = st.sidebar.number_input("Holding Cost ($/unit/year)", value=2.0)
order_cost = st.sidebar.number_input("Ordering Cost ($/order)", value=100.0)
service_level = st.sidebar.slider("Service Level (%)", 80, 99, 95)

# Z-score for service level
z_map = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.645, 98: 2.05, 99: 2.33}
z = z_map.get(service_level, 1.645)

# --- Calculations ---
# 1. EOQ / ROP (Continuous Review)
annual_demand = avg_demand * 365
eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost)
safety_stock_rop = z * std_demand * np.sqrt(lead_time)
rop = (avg_demand * lead_time) + safety_stock_rop

# 2. Periodic Review (P-System)
# Let's assume a weekly review period (T) for this example
review_period = st.sidebar.slider("Review Period (Days)", 1, 30, 7)
safety_stock_p = z * std_demand * np.sqrt(review_period + lead_time)
target_level = (avg_demand * (review_period + lead_time)) + safety_stock_p

# --- UI Layout ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Fixed Order Quantity (EOQ/ROP)")
    st.metric("Economic Order Quantity (Q)", f"{int(eoq)} units")
    st.metric("Reorder Point (ROP)", f"{int(rop)} units")
    st.write(f"**Safety Stock:** {int(safety_stock_rop)}")
    st.info("Triggered by inventory level falling to ROP.")

with col2:
    st.subheader("Periodic Review (P-System)")
    st.metric("Review Period (T)", f"{review_period} Days")
    st.metric("Target Inventory (S)", f"{int(target_level)} units")
    st.write(f"**Safety Stock:** {int(safety_stock_p)}")
    st.info("Triggered by time. Order = Target - Current Level.")

# --- Simulation ---
st.divider()
st.subheader("30-Day Inventory Simulation")

# Simple simulation logic
days = 30
inv_rop = [eoq + safety_stock_rop]
inv_p = [target_level]
demand_history = np.random.normal(avg_demand, std_demand, days)

# Basic Simulation Loop
for i in range(1, days):
    # ROP Logic
    new_rop = inv_rop[-1] - demand_history[i]
    if new_rop <= rop:
        new_rop += eoq
    inv_rop.append(max(0, new_rop))
    
    # P-System Logic
    new_p = inv_p[-1] - demand_history[i]
    if i % review_period == 0:
        order_qty = target_level - new_p
        new_p += order_qty
    inv_p.append(max(0, new_p))

# Plotting
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(inv_rop, label="Continuous (ROP)", marker='o', color='blue')
ax.plot(inv_p, label="Periodic (P-System)", marker='s', color='green')
ax.axhline(y=safety_stock_rop, color='r', linestyle='--', label="Safety Stock (ROP)")
ax.set_ylabel("Inventory Level")
ax.set_xlabel("Day")
ax.legend()
st.pyplot(fig)

st.write("""
### Key Differences Explained
* **Safety Stock:** Notice that the **Periodic Review** system typically requires higher safety stock. This is because it must protect against uncertainty during both the lead time *and* the review period.
* **Monitoring:** EOQ/ROP assumes you have a computer system (like an ERP) tracking every sale in real-time. Periodic is often used for manual counts or low-value items.
""")
