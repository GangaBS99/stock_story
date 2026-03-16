"""Agents page — agent registry with framework badges and trace links."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import httpx
import pandas as pd
import streamlit as st

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8500")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

FRAMEWORK_BADGE = {
    "pydantic_ai": "🦄 PydanticAI",
    "langchain": "🔗 LangChain",
    "openai": "🤖 OpenAI",
    "generic": "⚙️ Generic",
}


def get_agents() -> list[dict]:
    try:
        r = httpx.get(f"{CONTROL_PLANE_URL}/agents", timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def get_runs_by_agent(agent_name: str, limit: int = 500) -> list[dict]:
    try:
        r = httpx.get(
            f"{CONTROL_PLANE_URL}/runs",
            params={"agent_name": agent_name, "limit": limit},
            timeout=5.0,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


st.set_page_config(page_title="Agents", page_icon="🤖", layout="wide")
st.title("🤖 Agent Registry")

col_btn, _ = st.columns([1, 8])
with col_btn:
    if st.button("🔄 Refresh"):
        st.rerun()

agents = get_agents()

if not agents:
    st.info(
        "No agents registered yet.\n\n"
        "Connect an agent using one of the SDK adapters:\n"
        "```python\n"
        "from sdk.adapters.pydantic_ai import PydanticAIAdapter\n"
        "adapter = PydanticAIAdapter(agent=my_agent, name='my-agent')\n"
        "```"
    )
    st.stop()

# ── Registry table ────────────────────────────────────────────────────────────
rows = []
for agent in agents:
    framework = agent.get("framework", "generic")
    rows.append(
        {
            "Name": agent.get("name", ""),
            "Framework": FRAMEWORK_BADGE.get(framework, framework),
            "Description": agent.get("description", ""),
            "Version": agent.get("version", ""),
            "Evaluators": ", ".join(agent.get("evaluators", [])),
            "Registered": agent.get("registered_at", "")[:19].replace("T", " "),
        }
    )

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Per-agent drill-down ──────────────────────────────────────────────────────
st.divider()
selected_agent = st.selectbox(
    "Agent detail", [a["name"] for a in agents], index=0
)

if selected_agent:
    runs = get_runs_by_agent(selected_agent)

    total = len(runs)
    completed = sum(1 for r in runs if r["status"] == "completed")
    failed = sum(1 for r in runs if r["status"] == "failed")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total runs", total)
    c2.metric("Completed", completed)
    c3.metric("Failed", failed)

    if runs:
        st.subheader("Recent runs")
        rows2 = []
        for r in runs[:20]:
            trace_url = f"{LANGFUSE_HOST}/traces/{r['trace_id']}"
            rows2.append(
                {
                    "Status": r.get("status", ""),
                    "Latency (ms)": f"{r.get('latency_ms', 0):.0f}",
                    "Created": r.get("created_at", "")[:19].replace("T", " "),
                    "Trace": f"[open]({trace_url})",
                }
            )
        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)
        st.caption(
            f"[View all traces for {selected_agent} in Langfuse]"
            f"({LANGFUSE_HOST}/traces?name={selected_agent})"
        )
