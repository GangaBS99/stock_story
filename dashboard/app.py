"""
Agent Observability Platform — Streamlit Dashboard

Entry point. Renders the home / welcome page and provides shared
utilities used by all sub-pages.
"""
from __future__ import annotations

import os
from pathlib import Path

# Load .env before anything else so Langfuse and other SDKs pick up the keys.
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import streamlit as st

# ── page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agent Observability Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── shared helpers (importable by pages) ───────────────────────────────────
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://localhost:8500")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")


def cp_url(path: str) -> str:
    return f"{CONTROL_PLANE_URL}{path}"


def lf_url(path: str) -> str:
    return f"{LANGFUSE_HOST}{path}"


import httpx  # noqa: E402


def fetch_json(path: str, **params) -> list | dict | None:
    """GET from the control plane; returns None on any error."""
    try:
        r = httpx.get(cp_url(path), params=params, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ── home page ──────────────────────────────────────────────────────────────
st.title("🤖 Agent Observability Platform")
st.markdown(
    "A framework-agnostic control plane on top of **Langfuse** for tracing, "
    "evaluation, and dataset management across all your LLM agents."
)

col1, col2, col3 = st.columns(3)
with col1:
    st.info(
        "**Control Plane API**\n\n"
        f"[Open Swagger docs]({CONTROL_PLANE_URL}/docs)"
    )
with col2:
    st.success(
        "**Langfuse UI**\n\n"
        f"[Open Langfuse]({LANGFUSE_HOST})"
    )
with col3:
    st.warning(
        "**Quick links**\n\n"
        f"[Traces]({LANGFUSE_HOST}/traces) · "
        f"[Prompts]({LANGFUSE_HOST}/prompts) · "
        f"[Datasets]({LANGFUSE_HOST}/datasets)"
    )

st.divider()
st.markdown(
    "Use the **sidebar** to navigate between dashboard pages:\n"
    "- **Overview** — platform KPIs\n"
    "- **Eval Trends** — score trends over time\n"
    "- **Live Runs** — real-time run status\n"
    "- **Alerts** — threshold violations\n"
    "- **Experiments** — dataset run comparisons\n"
    "- **Agents** — agent registry"
)
