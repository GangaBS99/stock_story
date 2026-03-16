"""Live Runs page — auto-refreshing table of recent runs with trace links."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
import time

import httpx
import pandas as pd
import streamlit as st

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8500")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")


def get_runs(limit: int = 100, status: str | None = None) -> list[dict]:
    try:
        params: dict = {"limit": limit}
        if status and status != "All":
            params["status"] = status
        r = httpx.get(f"{CONTROL_PLANE_URL}/runs", params=params, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


st.set_page_config(page_title="Live Runs", page_icon="⚡", layout="wide")
st.title("⚡ Live Runs")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    status_filter = st.selectbox(
        "Status", ["All", "running", "pending", "completed", "failed"]
    )
with col2:
    limit = st.slider("Max rows", 10, 500, 100, 10)
with col3:
    st.write("")
    st.write("")
    auto_refresh = st.toggle("Auto-refresh", value=False)

placeholder = st.empty()

STATUS_EMOJI = {
    "completed": "✅",
    "failed": "❌",
    "running": "🔄",
    "pending": "⏳",
}


def render_table():
    runs = get_runs(limit=limit, status=status_filter)
    if not runs:
        placeholder.info("No runs found.")
        return

    rows = []
    for r in runs:
        status = r.get("status", "")
        trace_url = f"{LANGFUSE_HOST}/traces/{r['trace_id']}"
        rows.append(
            {
                "Status": f"{STATUS_EMOJI.get(status, '')} {status}",
                "Agent": r.get("agent_name", ""),
                "Run ID": r.get("run_id", "")[:8] + "…",
                "Latency (ms)": f"{r.get('latency_ms', 0):.0f}",
                "Created": r.get("created_at", "")[:19].replace("T", " "),
                "Trace": f"[open]({trace_url})",
                "Error": r.get("error") or "",
            }
        )

    df = pd.DataFrame(rows)
    placeholder.dataframe(df, use_container_width=True, hide_index=True)


render_table()

if auto_refresh:
    time.sleep(3)
    st.rerun()
