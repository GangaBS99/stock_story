"""Alerts page — threshold violations and error rate spikes."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
from datetime import datetime, timedelta

import httpx
import pandas as pd
import streamlit as st

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8500")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
DEFAULT_SCORE_THRESHOLD = float(os.getenv("ALERT_SCORE_THRESHOLD", "0.6"))
DEFAULT_ERROR_RATE_THRESHOLD = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.2"))


def get_runs(limit: int = 500) -> list[dict]:
    try:
        r = httpx.get(f"{CONTROL_PLANE_URL}/runs", params={"limit": limit}, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


st.set_page_config(page_title="Alerts", page_icon="🚨", layout="wide")
st.title("🚨 Alerts & Anomaly Detection")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    score_threshold = st.slider(
        "Score alert threshold", 0.0, 1.0, DEFAULT_SCORE_THRESHOLD, 0.05
    )
with col2:
    error_rate_threshold = st.slider(
        "Error rate threshold", 0.0, 1.0, DEFAULT_ERROR_RATE_THRESHOLD, 0.05
    )
with col3:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh"):
        st.rerun()

runs = get_runs()

if not runs:
    st.info("No runs yet. Alerts will appear once your agents start running.")
    st.stop()

df = pd.DataFrame(runs)
df["created_at"] = pd.to_datetime(df["created_at"])

alerts: list[dict] = []

# ── Error rate alert ─────────────────────────────────────────────────────────
total = len(df)
failed = len(df[df["status"] == "failed"])
error_rate = failed / total if total > 0 else 0.0

if error_rate >= error_rate_threshold:
    alerts.append(
        {
            "Severity": "🔴 HIGH",
            "Type": "Error Rate",
            "Detail": f"{error_rate * 100:.1f}% of runs failed (threshold: {error_rate_threshold * 100:.0f}%)",
            "Agent": "all",
            "Trace": "",
        }
    )

# ── Score threshold alerts ────────────────────────────────────────────────────
for run in runs:
    for score in run.get("scores", []):
        val = score.get("value", 1.0)
        if val < score_threshold:
            trace_url = f"{LANGFUSE_HOST}/traces/{run['trace_id']}"
            alerts.append(
                {
                    "Severity": "🟡 WARN" if val >= score_threshold * 0.7 else "🔴 HIGH",
                    "Type": "Low Score",
                    "Detail": f"{score['name']} = {val:.2f} (threshold: {score_threshold})",
                    "Agent": run.get("agent_name", ""),
                    "Trace": f"[open]({trace_url})",
                }
            )

# ── Recent spike detection (last 1 hour vs prior) ────────────────────────────
now = datetime.utcnow()
recent_mask = df["created_at"] > (now - timedelta(hours=1))
recent_df = df[recent_mask]
prior_df = df[~recent_mask]

if len(recent_df) > 5 and len(prior_df) > 5:
    recent_fail_rate = (recent_df["status"] == "failed").mean()
    prior_fail_rate = (prior_df["status"] == "failed").mean()
    if recent_fail_rate > prior_fail_rate * 2 and recent_fail_rate > 0.1:
        alerts.append(
            {
                "Severity": "🔴 HIGH",
                "Type": "Error Spike",
                "Detail": (
                    f"Failure rate jumped to {recent_fail_rate * 100:.1f}% "
                    f"in last hour (was {prior_fail_rate * 100:.1f}%)"
                ),
                "Agent": "all",
                "Trace": "",
            }
        )

if not alerts:
    st.success("✅ No active alerts. All metrics within thresholds.")
else:
    st.error(f"**{len(alerts)} alert(s) detected**")
    alert_df = pd.DataFrame(alerts)
    st.dataframe(alert_df, use_container_width=True, hide_index=True)

st.divider()

# ── Per-agent error rate table ────────────────────────────────────────────────
st.subheader("Per-agent error rates")
if "agent_name" in df.columns:
    agent_stats = (
        df.groupby("agent_name")
        .apply(
            lambda g: pd.Series(
                {
                    "total": len(g),
                    "failed": (g["status"] == "failed").sum(),
                    "error_rate": round((g["status"] == "failed").mean(), 3),
                }
            )
        )
        .reset_index()
    )
    st.dataframe(agent_stats, use_container_width=True, hide_index=True)
