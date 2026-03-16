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

score_names = df["score_name"].unique().tolist()
selected_scores = st.multiselect(
    "Score dimensions", score_names, default=score_names
)
df = df[df["score_name"].isin(selected_scores)]

# Line chart: score over time per dimension
st.subheader("Score over time")
fig = px.line(
    df,
    x="created_at",
    y="value",
    color="score_name",
    markers=True,
    labels={"value": "Score (0-1)", "created_at": "Time"},
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
