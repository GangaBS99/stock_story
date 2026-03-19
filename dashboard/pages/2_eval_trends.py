"""Eval Trends page — score trends over time, filterable by agent."""
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
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PK = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SK = os.getenv("LANGFUSE_SECRET_KEY", "")


def get_runs(agent_name: str | None = None, limit: int = 200) -> list[dict]:
    try:
        params = {"limit": limit}
        if agent_name:
            params["agent_name"] = agent_name
        r = httpx.get(
            f"{CONTROL_PLANE_URL}/runs", params=params, timeout=5.0
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def get_agents() -> list[str]:
    try:
        r = httpx.get(f"{CONTROL_PLANE_URL}/agents", timeout=5.0)
        r.raise_for_status()
        return ["All"] + [a["name"] for a in r.json()]
    except Exception:
        return ["All"]


st.set_page_config(page_title="Eval Trends", page_icon="📈", layout="wide")
st.title("📈 Eval Score Trends")

col_filter, col_btn = st.columns([4, 1])
with col_filter:
    agents = get_agents()
    selected_agent = st.selectbox("Filter by agent", agents)
with col_btn:
    st.write("")
    st.write("")
    if st.button("🔄 Refresh"):
        st.rerun()

agent_param = None if selected_agent == "All" else selected_agent
runs = get_runs(agent_name=agent_param)

if not runs:
    st.info("No runs with scores found. Ensure evaluators are configured.")
    st.stop()

# Flatten runs + scores into a long-form DataFrame
rows = []
for run in runs:
    for score in run.get("scores", []):
        rows.append(
            {
                "created_at": run["created_at"],
                "agent_name": run["agent_name"],
                "score_name": score["name"],
                "value": score["value"],
                "trace_id": run["trace_id"],
            }
        )

if not rows:
    st.info(
        "Runs found but no scores attached yet. "
        "Scores appear after the eval pipeline processes a run."
    )
    st.stop()

df = pd.DataFrame(rows)
df["created_at"] = pd.to_datetime(df["created_at"])
df = df.sort_values("created_at")

score_names = df["score_name"].unique().tolist()
selected_scores = st.multiselect(
    "Score dimensions", score_names, default=score_names
)
df = df[df["score_name"].isin(selected_scores)]

# Trend controls
st.subheader("Score over time")
mode_col, bucket_col = st.columns([2, 2])
with mode_col:
    trend_mode = st.radio(
        "Trend mode",
        ["Aggregated", "Raw runs"],
        horizontal=True,
        help="Aggregated smooths noisy one-off scores and mixed agents.",
    )
with bucket_col:
    bucket = st.selectbox(
        "Time bucket",
        ["Auto", "5 min", "15 min", "1 hour", "1 day"],
        index=0,
    )

freq_map = {
    "5 min": "5min",
    "15 min": "15min",
    "1 hour": "1h",
    "1 day": "1d",
}

if trend_mode == "Aggregated":
    # Auto-bucket selection based on visible timespan.
    if bucket == "Auto":
        span_seconds = (df["created_at"].max() - df["created_at"].min()).total_seconds()
        if span_seconds <= 3600:
            freq = "5min"
        elif span_seconds <= 6 * 3600:
            freq = "15min"
        elif span_seconds <= 3 * 24 * 3600:
            freq = "1h"
        else:
            freq = "1d"
    else:
        freq = freq_map[bucket]

    agg_df = df.copy()
    agg_df["time_bucket"] = agg_df["created_at"].dt.floor(freq)
    group_cols = ["time_bucket", "score_name"]
    if selected_agent == "All":
        group_cols.append("agent_name")

    agg_df = (
        agg_df.groupby(group_cols, as_index=False)
        .agg(
            value=("value", "mean"),
            samples=("value", "count"),
        )
    )

    if selected_agent == "All":
        agg_df["series"] = agg_df["score_name"] + " | " + agg_df["agent_name"]
    else:
        agg_df["series"] = agg_df["score_name"]

    fig = px.line(
        agg_df,
        x="time_bucket",
        y="value",
        color="series",
        markers=True,
        labels={"value": "Score (0-1)", "time_bucket": "Time", "series": "Series"},
        hover_data={
            "agent_name": True,
            "score_name": True,
            "samples": True,
            "series": False,
            "time_bucket": True,
            "value": ":.3f",
        },
    )
else:
    raw_df = df.copy()
    if selected_agent == "All":
        raw_df["series"] = raw_df["score_name"] + " | " + raw_df["agent_name"]
    else:
        raw_df["series"] = raw_df["score_name"]

    fig = px.line(
        raw_df,
        x="created_at",
        y="value",
        color="series",
        markers=True,
        labels={"value": "Score (0-1)", "created_at": "Time", "series": "Series"},
        hover_data={
            "agent_name": True,
            "score_name": True,
            "trace_id": True,
            "series": False,
            "created_at": True,
            "value": ":.3f",
        },
    )

fig.update_yaxes(range=[0, 1])
fig.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# Average scores per agent
st.subheader("Average scores by agent")
avg_df = (
    df.groupby(["agent_name", "score_name"])["value"]
    .mean()
    .round(3)
    .reset_index()
)
fig2 = px.bar(
    avg_df,
    x="agent_name",
    y="value",
    color="score_name",
    barmode="group",
    labels={"value": "Avg score"},
)
fig2.update_yaxes(range=[0, 1])
fig2.update_layout(margin=dict(t=20, b=20))
st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.caption(
    f"Deep-dive into individual traces in [Langfuse UI]({LANGFUSE_HOST}/traces)"
)
