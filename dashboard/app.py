"""
AquaSentinel - Dashboard V1
Source-aware water intelligence and outlet monitoring for RO systems.
Implements the Dashboard V1 Specification from docs/DASHBOARD_V1.md.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="AquaSentinel | Water Quality Intelligence",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
DEVICE_ID = os.getenv("DEFAULT_DEVICE_ID", "AQUASENTINEL-01")

# ==============================================================================
# API CLIENT HELPERS
# ==============================================================================
@st.cache_data(ttl=5)
def get_health() -> dict | None:
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=2.0)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

@st.cache_data(ttl=60)
def get_locations(source_type: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}/locations", params={"source_type": source_type}, timeout=4.0)
        return r.json().get("locations", []) if r.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=60)
def get_historical_context(source_type: str, location_id: str) -> dict | None:
    try:
        r = requests.get(
            f"{API_BASE_URL}/historical-context",
            params={"source_type": source_type, "location_id": location_id},
            timeout=5.0
        )
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def get_latest_outlet(device_id: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE_URL}/outlet/latest", params={"device_id": device_id}, timeout=3.0)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def get_outlet_history(device_id: str, hours: int = 1) -> list[dict]:
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        r = requests.get(
            f"{API_BASE_URL}/outlet/history",
            params={
                "device_id": device_id,
                "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "limit": 1000
            },
            timeout=5.0
        )
        return r.json().get("items", []) if r.status_code == 200 else []
    except Exception:
        return []

def get_outlet_summary(device_id: str, limit: int = 10) -> list[dict]:
    try:
        r = requests.get(
            f"{API_BASE_URL}/outlet/summary",
            params={"device_id": device_id, "window": "30m", "limit": limit},
            timeout=4.0
        )
        return r.json().get("items", []) if r.status_code == 200 else []
    except Exception:
        return []

# ==============================================================================
# SIDEBAR CONTROLS
# ==============================================================================
with st.sidebar:
    st.title("💧 AquaSentinel")
    st.markdown("**RO Water Intelligence Node**")
    st.divider()

    st.subheader("System Connectivity")
    health = get_health()
    if health:
        st.success(f"Backend: ONLINE ({health.get('api_version', 'v1')})")
    else:
        st.error("Backend: OFFLINE (Check FastAPI server)")

    st.text_input("Device ID", value=DEVICE_ID, key="active_device_id")
    active_device = st.session_state.active_device_id

    st.divider()
    st.subheader("Dashboard Controls")
    auto_refresh = st.checkbox("Auto Refresh (every 5s)", value=True)
    if st.button("🔄 Refresh Data Now"):
        st.rerun()

    st.divider()
    st.caption("ESP32-WROOM-32E (Wi-Fi + BT) Node")
    st.caption("Firmware: v0.1.0 | Protocol: AquaSentinel REST v1.0")

# If auto-refresh enabled, set rerun timer
if auto_refresh:
    # Use streamlit autorefresh or empty container
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, key="data_refresh")
    except ImportError:
        pass

# ==============================================================================
# MAIN DASHBOARD HEADER
# ==============================================================================
st.markdown("## 💧 AquaSentinel: Source-Aware RO Monitoring")
st.markdown(
    "*Combines regional historical source intelligence with live telemetry from the treated-water outlet.*"
)

# Fetch latest reading
latest_data = get_latest_outlet(active_device)
device_online = False
last_received_str = "No data recorded"

if latest_data and latest_data.get("data_status") in ("available", "stale"):
    device_online = latest_data.get("data_status") == "available"
    rec = latest_data.get("received_at", "")
    age = latest_data.get("age_seconds", 0)
    last_received_str = f"{rec} ({age:.1f}s ago)"

col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    if device_online:
        st.success("🟢 Node Status: ONLINE")
    else:
        st.warning(f"🟡 Node Status: {latest_data.get('data_status', 'DISCONNECTED').upper() if latest_data else 'OFFLINE'}")
with col_h2:
    st.info(f"📡 Target Device: `{active_device}`")
with col_h3:
    st.metric("Latest Ingestion", last_received_str)

st.divider()

# ==============================================================================
# SECTION 1: LIVE OUTLET WATER MONITORING
# ==============================================================================
st.subheader("1. Live Outlet Water Monitoring")
st.caption("Real-time measurements from the ESP32-WROOM-32E sensor node positioned at the RO treated-water outlet.")

measurements = latest_data.get("measurements", {}) if latest_data else {}
tds_m = measurements.get("tds", {})
ph_m = measurements.get("ph", {})
turb_m = measurements.get("turbidity", {})
temp_m = measurements.get("temperature", {})

c1, c2, c3, c4 = st.columns(4)

with c1:
    tds_val = tds_m.get("value")
    st.metric(
        label="TDS (Total Dissolved Solids)",
        value=f"{tds_val} ppm" if tds_val is not None else "—",
        help="Estimated dissolved ionic content measured by analog probe."
    )
    st.caption(f"Status: `{tds_m.get('status', 'no_data')}` | Calibrated: `{tds_m.get('calibrated', False)}`")

with c2:
    ph_val = ph_m.get("value")
    st.metric(
        label="pH Level",
        value=f"{ph_val} pH" if ph_val is not None else "—",
        help="pH measurement (Requires optional analog pH probe)."
    )
    st.caption(f"Status: `{ph_m.get('status', 'unavailable')}` (Sensor not fitted)")

with c3:
    turb_val = turb_m.get("value")
    unit = turb_m.get("unit", "raw")
    st.metric(
        label="Turbidity",
        value=f"{turb_val} {unit}" if turb_val is not None else "—",
        help="Water cloudiness and suspended particle measurement."
    )
    st.caption(f"Status: `{turb_m.get('status', 'no_data')}` | Calibrated: `{turb_m.get('calibrated', False)}`")

with c4:
    temp_val = temp_m.get("value")
    st.metric(
        label="Water Temperature",
        value=f"{temp_val} °C" if temp_val is not None else "—",
        help="DS18B20 digital waterproof probe reading."
    )
    st.caption(f"Status: `{temp_m.get('status', 'no_data')}` | Calibrated: `{temp_m.get('calibrated', True)}`")

# Time-series History Charts
st.markdown("#### Outlet Sensor Trends")
time_filter = st.radio(
    "Time Range:",
    options=[("1 Hour", 1), ("6 Hours", 6), ("24 Hours", 24), ("7 Days", 168)],
    format_func=lambda x: x[0],
    horizontal=True,
    key="time_range_select"
)
hours_to_fetch = time_filter[1]

history_items = get_outlet_history(active_device, hours=hours_to_fetch)

if history_items:
    rows = []
    for item in history_items:
        t = item["captured_at"]
        m = item.get("measurements", {})
        rows.append({
            "Timestamp": pd.to_datetime(t),
            "Sequence": item.get("sequence"),
            "TDS (ppm)": m.get("tds", {}).get("value"),
            "pH": m.get("ph", {}).get("value"),
            "Turbidity (V/NTU)": m.get("turbidity", {}).get("value"),
            "Temperature (°C)": m.get("temperature", {}).get("value")
        })
    df_hist = pd.DataFrame(rows)

    chart_tab1, chart_tab2, chart_tab3 = st.tabs(["TDS Trend", "Turbidity Trend", "Temperature Trend"])
    
    with chart_tab1:
        fig_tds = px.line(
            df_hist, x="Timestamp", y="TDS (ppm)",
            title="Outlet TDS over Time (ppm)",
            markers=True, line_shape="spline",
            color_discrete_sequence=["#1f77b4"]
        )
        fig_tds.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_tds, use_container_width=True)

    with chart_tab2:
        fig_turb = px.line(
            df_hist, x="Timestamp", y="Turbidity (V/NTU)",
            title="Outlet Optical Turbidity over Time",
            markers=True, line_shape="spline",
            color_discrete_sequence=["#ff7f0e"]
        )
        fig_turb.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_turb, use_container_width=True)

    with chart_tab3:
        fig_temp = px.line(
            df_hist, x="Timestamp", y="Temperature (°C)",
            title="Water Temperature over Time (°C)",
            markers=True, line_shape="spline",
            color_discrete_sequence=["#2ca02c"]
        )
        fig_temp.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig_temp, use_container_width=True)
else:
    st.info("No time-series history available in the selected window. Telemetry is saved automatically as readings arrive.")

# 30-Minute Analytical Summaries
st.markdown("#### 30-Minute Analytical Aggregation Windows")
st.caption("Aggregates closed 30-minute UTC windows [hh:00, hh:30) and [hh:30, next hh:00) with minimum coverage verification.")
summaries = get_outlet_summary(active_device, limit=5)
if summaries:
    sum_rows = []
    for s in summaries:
        w_start = s.get("window_start", "")
        w_end = s.get("window_end", "")
        params = s.get("parameters", {})
        tds_p = params.get("tds", {})
        turb_p = params.get("turbidity", {})
        temp_p = params.get("temperature", {})
        sum_rows.append({
            "Window": f"{w_start[11:16]} - {w_end[11:16]} UTC",
            "Coverage": f"{s.get('data_coverage', 0) * 100:.1f}%",
            "Samples": s.get("valid_sample_count", 0),
            "TDS Mean": f"{tds_p.get('mean'):.1f} ppm" if tds_p.get("mean") is not None else "—",
            "Turbidity Mean": f"{turb_p.get('mean'):.3f}" if turb_p.get("mean") is not None else "—",
            "Temp Mean": f"{temp_p.get('mean'):.1f} °C" if temp_p.get("mean") is not None else "—",
            "Completeness": "Complete" if s.get("is_complete") else "Partial"
        })
    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True)
else:
    st.caption("No closed 30-minute analytical windows generated yet. Windows close automatically on the hour and half-hour.")

st.divider()

# ==============================================================================
# SECTION 2: HISTORICAL SOURCE INTELLIGENCE
# ==============================================================================
st.subheader("2. Regional Historical Source Intelligence")
st.markdown(
    "Groundwater (CGWB) and Surface Water (CPCB) baseline profiles. "
    "*Historical context represents regional aquifer/river surveys and must not be confused with real-time inlet sensor readings.*"
)

col_s1, col_s2 = st.columns(2)
with col_s1:
    source_choice = st.selectbox(
        "Water Source Type",
        options=["groundwater", "surface_water"],
        format_func=lambda x: "Groundwater (CGWB India)" if x == "groundwater" else "Surface Water (CPCB India)"
    )

locations_list = get_locations(source_choice)
loc_options = {f"{loc.get('display_name', loc.get('location_id'))}": loc.get("location_id") for loc in locations_list}

with col_s2:
    if loc_options:
        selected_label = st.selectbox("Select Station / District", options=list(loc_options.keys()))
        selected_loc_id = loc_options[selected_label]
    else:
        st.info("Loading stations from dataset...")
        selected_loc_id = None

if selected_loc_id:
    hist_ctx = get_historical_context(source_choice, selected_loc_id)
    if hist_ctx:
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Station / Location", hist_ctx.get("matched_location", selected_loc_id))
        h2.metric("Dataset Agency", hist_ctx.get("agency", "CGWB/CPCB"))
        h3.metric("Observations Count", hist_ctx.get("observation_count", 0))
        sample_range = hist_ctx.get("sample_date_range", {})
        h4.metric("Sampling Period", f"{sample_range.get('start', '—')} to {sample_range.get('end', '—')}")

        # Parameter details table
        params = hist_ctx.get("parameters", {})
        if params:
            p_rows = []
            for pname, pinfo in params.items():
                p_rows.append({
                    "Parameter": pname.upper(),
                    "Unit": pinfo.get("unit", "—"),
                    "Mean": round(pinfo.get("mean", 0), 2) if pinfo.get("mean") is not None else "—",
                    "Median": round(pinfo.get("median", 0), 2) if pinfo.get("median") is not None else "—",
                    "Min": pinfo.get("min", "—"),
                    "Max": pinfo.get("max", "—"),
                    "Std Dev": round(pinfo.get("std_dev", 0), 2) if pinfo.get("std_dev") is not None else "—",
                    "Valid Samples": pinfo.get("valid_count", "—"),
                    "Latest Date": pinfo.get("latest_valid_date", "—")
                })
            st.dataframe(pd.DataFrame(p_rows), use_container_width=True)
    else:
        st.warning("No historical observations found for the selected station.")

st.divider()

# ==============================================================================
# SECTION 3: R&D MODULES (PLANNED)
# ==============================================================================
st.subheader("3. Advanced Analytics & RO Decision Engine (R&D)")
r1, r2 = st.columns(2)

with r1:
    st.info("🧪 **Filter Performance & Maintenance Monitoring — R&D IN PROGRESS**")
    st.markdown(
        "Planned indirect assessment of possible filtration-performance changes using persistent outlet "
        "measurement trends and maintenance records.\n\n"
        "> *Note: The four outlet sensors cannot directly identify a failed filter stage or confirm membrane fouling.*"
    )

with r2:
    st.info("🧠 **RO Evidence Fusion & Decision Engine — R&D IN PROGRESS**")
    st.markdown(
        "Planned evidence fusion of historical source context, live outlet measurements and filter-performance "
        "indicators to generate explainable RO operating recommendations.\n\n"
        "> *Note: No automatic purifier control is active in this prototype.*"
    )

