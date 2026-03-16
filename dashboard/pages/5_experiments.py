"""Experiments page — run and compare dataset experiments from the UI."""
from __future__ import annotations

import io
import os
import sys
import contextlib
import threading
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
DEFAULT_AGENT_URL = os.getenv("AGENT_URL", "http://127.0.0.1:7000")

st.set_page_config(page_title="Experiments", page_icon="🧪", layout="wide")
st.title("🧪 Dataset Experiments")


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _lf_client():
    from langfuse import Langfuse
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=LANGFUSE_HOST,
    )


@st.cache_data(ttl=30)
def fetch_dataset_names() -> list[str]:
    try:
        client = _lf_client()
        page = client.api.datasets.list(limit=100)
        items = page.data if hasattr(page, "data") else []
        return sorted(d.name for d in items if hasattr(d, "name"))
    except Exception:
        return []


@st.cache_data(ttl=20)
def fetch_dataset_runs(dataset_name: str) -> list[dict]:
    try:
        client = _lf_client()
        runs = client.get_dataset_runs(dataset_name=dataset_name)
        items = runs.data if hasattr(runs, "data") else (runs if isinstance(runs, list) else [])
        return [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in items]
    except Exception:
        return []


def _run_experiment_thread(dataset_name, experiment_name, agent_url, result_holder):
    """Run in a background thread; write logs and result URL into result_holder."""
    log_buf = io.StringIO()
    result_holder["status"] = "running"
    result_holder["logs"] = ""
    result_holder["url"] = ""
    result_holder["error"] = ""

    try:
        # import the runner (uses the project venv where langfuse + google-genai are installed)
        from scripts.run_experiment import run_experiment_cmd as _run

        # capture stdout so we can surface logs in the UI
        with contextlib.redirect_stdout(log_buf):
            _run(
                dataset_name=dataset_name,
                experiment_name=experiment_name,
                agent_url=agent_url,
            )

        logs = log_buf.getvalue()
        result_holder["logs"] = logs

        # extract the Langfuse URL from the printed output if present
        for line in logs.splitlines():
            if "localhost:3000" in line and "/datasets/" in line:
                result_holder["url"] = line.strip().replace("View results : ", "").strip()
                break

        result_holder["status"] = "done"

    except Exception as exc:
        result_holder["logs"] = log_buf.getvalue()
        result_holder["error"] = str(exc)
        result_holder["status"] = "error"


# ─────────────────────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────────────────────

if "exp_result" not in st.session_state:
    st.session_state.exp_result = {"status": "idle", "logs": "", "url": "", "error": ""}
if "exp_thread" not in st.session_state:
    st.session_state.exp_thread = None


# ─────────────────────────────────────────────────────────────
# ① Run Experiment section
# ─────────────────────────────────────────────────────────────

st.subheader("▶ Run Experiment")

dataset_names = fetch_dataset_names()

with st.form("run_experiment_form"):
    col1, col2 = st.columns(2)

    with col1:
        if dataset_names:
            dataset = st.selectbox(
                "Dataset",
                options=dataset_names,
                help="Dataset created in Langfuse UI or via seed script",
            )
        else:
            dataset = st.text_input(
                "Dataset name",
                value="morning-note-benchmark",
                help="No datasets found — type the name manually",
            )

        experiment_name = st.text_input(
            "Experiment name",
            value="run-v1",
            help="Label shown in Langfuse Experiments table (use version names like gemini-v1, gpt4o-v2)",
        )

    with col2:
        agent_url = st.text_input(
            "Agent URL",
            value=DEFAULT_AGENT_URL,
            help="Base URL of your agent's /process_message endpoint",
        )
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("**Evaluators included automatically:**")
        st.markdown("- `output_present` — checks agent produced output")
        st.markdown("- `answer_token_overlap` — word overlap vs ground truth")
        st.markdown("- `answer_recall` — reference coverage")
        st.markdown("- `answer_llm_match` — Gemini judge score")

    submitted = st.form_submit_button("🚀 Run Experiment", type="primary", use_container_width=True)


if submitted:
    if not dataset:
        st.error("Please select or enter a dataset name.")
    elif not experiment_name.strip():
        st.error("Please enter an experiment name.")
    elif st.session_state.exp_result.get("status") == "running":
        st.warning("An experiment is already running. Wait for it to finish.")
    else:
        result_holder = {"status": "idle", "logs": "", "url": "", "error": ""}
        st.session_state.exp_result = result_holder
        t = threading.Thread(
            target=_run_experiment_thread,
            args=(dataset, experiment_name.strip(), agent_url, result_holder),
            daemon=True,
        )
        st.session_state.exp_thread = t
        t.start()
        st.rerun()


# ─────────────────────────────────────────────────────────────
# Status display (live while running, final when done)
# ─────────────────────────────────────────────────────────────

result = st.session_state.exp_result
exp_status = result.get("status", "idle")

if exp_status == "running":
    thread: threading.Thread | None = st.session_state.get("exp_thread")
    is_alive = thread.is_alive() if thread else False

    with st.status("⏳ Experiment running… this may take a few minutes", expanded=True):
        st.write("Calling agent for each dataset item and scoring results…")
        logs_so_far = result.get("logs", "")
        if logs_so_far:
            st.code(logs_so_far, language=None)

    if not is_alive:
        # thread finished — update status based on what was written
        if result.get("error"):
            result["status"] = "error"
        else:
            result["status"] = "done"
        st.rerun()
    else:
        # auto-refresh every 3 seconds while running
        import time
        time.sleep(3)
        st.rerun()

elif exp_status == "done":
    st.success("✅ Experiment completed!")
    logs = result.get("logs", "")
    if logs:
        with st.expander("📋 Execution logs", expanded=False):
            st.code(logs, language=None)

    url = result.get("url", "")
    if url:
        st.markdown(f"### 🔗 [View results in Langfuse]({url})")
    else:
        st.markdown(
            f"### 🔗 [View results in Langfuse]({LANGFUSE_HOST})"
            " → Datasets → your dataset → Experiments"
        )

    if st.button("Run another experiment"):
        st.session_state.exp_result = {"status": "idle", "logs": "", "url": "", "error": ""}
        st.rerun()

elif exp_status == "error":
    st.error("❌ Experiment failed")
    st.code(result.get("error", "Unknown error"), language=None)
    logs = result.get("logs", "")
    if logs:
        with st.expander("📋 Logs before failure"):
            st.code(logs, language=None)
    if st.button("Try again"):
        st.session_state.exp_result = {"status": "idle", "logs": "", "url": "", "error": ""}
        st.rerun()


# ─────────────────────────────────────────────────────────────
# ② Past Runs viewer
# ─────────────────────────────────────────────────────────────

st.divider()
st.subheader("📊 Past Experiment Runs")

col_ds, col_refresh = st.columns([4, 1])
with col_ds:
    view_dataset = st.selectbox(
        "View runs for dataset",
        options=dataset_names or ["morning-note-benchmark"],
        key="view_dataset",
    )
with col_refresh:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="refresh_runs"):
        st.cache_data.clear()
        st.rerun()

if view_dataset:
    st.markdown(
        f"[Open in Langfuse ↗]({LANGFUSE_HOST}/datasets/{view_dataset})",
    )

    runs = fetch_dataset_runs(view_dataset)

    if not runs:
        st.info("No experiment runs found for this dataset yet.")
    else:
        import pandas as pd

        # Build summary table
        rows = []
        for r in runs:
            rows.append({
                "Run name": r.get("name", r.get("run_name", "")),
                "Description": r.get("description", ""),
                "Items": r.get("dataset_run_item_count", "—"),
                "Avg latency (s)": r.get("avg_latency", "—"),
                "Avg cost ($)": r.get("avg_total_cost", "—"),
                "Created": str(r.get("created_at", ""))[:19],
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Score comparison chart if scores available
        score_rows = []
        for r in runs:
            run_name = r.get("name", r.get("run_name", ""))
            for score in r.get("scores", []) or []:
                score_rows.append({
                    "run": run_name,
                    "metric": score.get("name", ""),
                    "value": score.get("value", 0),
                })

        if score_rows:
            import plotly.express as px
            score_df = pd.DataFrame(score_rows)
            fig = px.bar(
                score_df,
                x="run",
                y="value",
                color="metric",
                barmode="group",
                title="Score comparison across experiment runs",
                labels={"run": "Experiment", "value": "Score (0–1)"},
            )
            fig.update_yaxes(range=[0, 1])
            st.plotly_chart(fig, use_container_width=True)
