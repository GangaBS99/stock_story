"""Overview page — platform-wide KPI cards."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8500")


def get(path: str, **params):
    try:
        r = httpx.get(f"{CONTROL_PLANE_URL}{path}", params=params, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")
st.title("📊 Platform Overview")

if st.button("🔄 Refresh"):
    st.rerun()

# ── KPI cards ───────────────────────────────────────────────────────────────
stats = get("/runs/stats") or {}
runs = get("/runs", limit=500) or []

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Runs", stats.get("total", 0))
col2.metric(
    "Success Rate",
    f"{stats.get('success_rate', 0) * 100:.1f}%",
    delta=None,
)
col3.metric("Avg Latency", f"{stats.get('avg_latency_ms', 0):.0f} ms")
col4.metric("Failed Runs", stats.get("failed", 0))

st.divider()

if not runs:
    st.info("No runs yet. Connect an agent and make some calls to see data here.")
    st.stop()

# ── Runs over time ───────────────────────────────────────────────────────────
df = pd.DataFrame(runs)
df["created_at"] = pd.to_datetime(df["created_at"])
df["date"] = df["created_at"].dt.date

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Runs per day")
    daily = df.groupby("date").size().reset_index(name="runs")
    fig = px.bar(daily, x="date", y="runs", color_discrete_sequence=["#6366f1"])
    fig.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Status breakdown")
    status_counts = df["status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    color_map = {
        "completed": "#22c55e",
        "failed": "#ef4444",
        "running": "#f59e0b",
        "pending": "#94a3b8",
    }
    fig2 = px.pie(
        status_counts,
        names="status",
        values="count",
        color="status",
        color_discrete_map=color_map,
    )
    fig2.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig2, use_container_width=True)

# ── Latency by agent ─────────────────────────────────────────────────────────
st.subheader("Avg latency by agent")
if "agent_name" in df.columns and "latency_ms" in df.columns:
    lat_df = (
        df.groupby("agent_name")["latency_ms"]
        .mean()
        .round(1)
        .reset_index()
        .rename(columns={"latency_ms": "avg_latency_ms"})
    )
    fig3 = px.bar(
        lat_df,
        x="agent_name",
        y="avg_latency_ms",
        color_discrete_sequence=["#8b5cf6"],
    )
    fig3.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig3, use_container_width=True)
