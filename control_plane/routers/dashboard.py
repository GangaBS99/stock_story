"""
Dashboard aggregation endpoints.

All data is sourced from the in-memory RunTracker and the Langfuse SDK.
The React frontend polls these endpoints every 10 seconds.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_runs():
    from control_plane.runner import tracker
    return tracker.list_all(limit=500)


def _get_scores_for_runs(runs) -> dict[str, list[dict]]:
    """Map run_id → list of score dicts from attached scores."""
    result: dict[str, list[dict]] = {}
    for r in runs:
        result[r.run_id] = [s.model_dump() for s in r.scores]
    return result


def _percentile(data: list[float], pct: int) -> float:
    if not data:
        return 0.0
    data_sorted = sorted(data)
    idx = int(len(data_sorted) * pct / 100)
    idx = min(idx, len(data_sorted) - 1)
    return round(data_sorted[idx], 2)


def _score_name_matches(name: str, target: str) -> bool:
    """Match plain and namespaced score names (e.g. llm_judge.accuracy)."""
    return name == target or name.endswith(f".{target}")


def _avg_score_by_name(runs, score_name: str) -> float:
    values = []
    for r in runs:
        for s in r.scores:
            if _score_name_matches(s.name, score_name):
                values.append(s.value)
    return round(statistics.mean(values), 3) if values else 0.0


def _has_score_by_name(runs, score_name: str) -> bool:
    for r in runs:
        for s in r.scores:
            if _score_name_matches(s.name, score_name):
                return True
    return False


def _langfuse_traces(limit: int = 100) -> list[dict]:
    try:
        from control_plane.langfuse_client import get_traces
        return get_traces(limit=limit)
    except Exception:
        return []


def _extract_trace_id(trace: dict) -> str | None:
    return (
        trace.get("id")
        or trace.get("trace_id")
        or trace.get("traceId")
    )


def _normalize_trace_id(trace_id: str) -> str:
    tid = str(trace_id or "").strip()
    if len(tid) == 36 and tid.count("-") == 4:
        return tid.replace("-", "")
    return tid


def _extract_trace_cost(trace: dict) -> float:
    cost = trace.get("total_cost")
    if cost is None:
        cost = trace.get("totalCost")
    try:
        return float(cost or 0.0)
    except Exception:
        return 0.0


def _extract_trace_latency_ms(trace: dict) -> float:
    latency = trace.get("latency")
    if latency is None:
        latency = trace.get("latency_ms")
    if latency is None:
        latency = trace.get("latencyMs")
    if latency is None:
        latency = trace.get("duration")
    try:
        return float(latency or 0.0)
    except Exception:
        return 0.0


def _extract_trace_timestamp(trace: dict) -> str:
    ts = trace.get("timestamp")
    if ts is None:
        ts = trace.get("created_at")
    if ts is None:
        ts = trace.get("createdAt")
    return str(ts or "")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_trace_turns(trace: dict) -> int:
    metadata = trace.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    attributes = metadata_dict.get("attributes")
    attributes_dict = attributes if isinstance(attributes, dict) else {}

    candidates = [
        metadata_dict.get("turns"),
        metadata_dict.get("decision_turns"),
        attributes_dict.get("turns"),
        attributes_dict.get("decision_turns"),
        attributes_dict.get("pydantic_ai.new_message_index"),
    ]
    for value in candidates:
        try:
            if value is not None:
                return int(value)
        except Exception:
            pass
    return 0


def _normalize_observations(raw_observations: Any) -> list[dict]:
    if not isinstance(raw_observations, list):
        return []
    nodes: list[dict] = []
    for obs in raw_observations:
        if not isinstance(obs, dict):
            continue
        nodes.append(
            {
                "id": str(obs.get("id") or ""),
                "parent_id": str(
                    obs.get("parentObservationId")
                    or obs.get("parent_observation_id")
                    or ""
                ),
                "type": str(obs.get("type") or ""),
                "name": str(obs.get("name") or ""),
                "level": str(obs.get("level") or ""),
                "start_time": str(obs.get("startTime") or obs.get("start_time") or ""),
                "end_time": str(obs.get("endTime") or obs.get("end_time") or ""),
                "input_preview": _preview_value(obs.get("input")),
                "output_preview": _preview_value(obs.get("output")),
                "metadata": obs.get("metadata") or {},
            }
        )
    return nodes


def _estimate_turns_from_observations(observations: list[dict]) -> int:
    # For tree-like agent runs, generation + tool nodes are a strong proxy for "turns".
    count = 0
    for obs in observations:
        obs_type = str(obs.get("type") or "").upper()
        if obs_type in {"GENERATION", "TOOL"}:
            count += 1
    return count


def _nearest_trace_for_run(run: Any, traces: list[dict], max_delta_seconds: int = 900) -> dict | None:
    target_ts = run.created_at
    if target_ts.tzinfo is None:
        target_ts = target_ts.replace(tzinfo=timezone.utc)

    nearest_same_agent: tuple[float, dict] | None = None
    nearest_any_agent: tuple[float, dict] | None = None
    run_agent = str(run.agent_name).strip().lower()
    for candidate in traces:
        candidate_ts = _parse_datetime(_extract_trace_timestamp(candidate))
        if candidate_ts is None:
            continue
        if candidate_ts.tzinfo is None:
            candidate_ts = candidate_ts.replace(tzinfo=timezone.utc)
        delta = abs((candidate_ts - target_ts).total_seconds())
        if delta > max_delta_seconds:
            continue

        if nearest_any_agent is None or delta < nearest_any_agent[0]:
            nearest_any_agent = (delta, candidate)

        candidate_agent = _extract_agent_name_from_trace(candidate).strip().lower()
        if candidate_agent == run_agent:
            if nearest_same_agent is None or delta < nearest_same_agent[0]:
                nearest_same_agent = (delta, candidate)

    picked = nearest_same_agent or nearest_any_agent
    return picked[1] if picked else None


def _preview_value(value: Any, max_len: int = 180) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _extract_agent_name_from_trace(trace: dict) -> str:
    metadata = trace.get("metadata")
    metadata_dict = metadata if isinstance(metadata, dict) else {}
    attributes = metadata_dict.get("attributes")
    attributes_dict = attributes if isinstance(attributes, dict) else {}

    candidates = [
        metadata_dict.get("agent_name"),
        metadata_dict.get("agent"),
        metadata_dict.get("agentName"),
        attributes_dict.get("agent_name"),
        attributes_dict.get("agent"),
        attributes_dict.get("agentName"),
        attributes_dict.get("gen_ai.agent.name"),
        trace.get("name"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return ""


def _trace_cost_map(limit: int = 500) -> dict[str, float]:
    traces = _langfuse_traces(limit=limit)
    result: dict[str, float] = {}
    for t in traces:
        trace_id = _extract_trace_id(t)
        if trace_id:
            result[trace_id] = _extract_trace_cost(t)
    return result


# ─────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────

@router.get("/kpis", summary="Top-bar KPI metrics")
def get_kpis() -> dict:
    from sdk.schemas import RunStatus
    runs = _get_runs()

    total = len(runs)
    completed = sum(1 for r in runs if r.status == RunStatus.COMPLETED)
    failed = sum(1 for r in runs if r.status == RunStatus.FAILED)
    tsr = round(completed / total * 100, 1) if total else 0.0

    latencies = [r.latency_ms for r in runs if r.latency_ms > 0]
    p95_latency = _percentile(latencies, 95)
    avg_latency = round(statistics.mean(latencies), 1) if latencies else 0.0

    # Prefer explicit tool_accuracy if provided, otherwise fall back to judged accuracy.
    tool_accuracy_avg = _avg_score_by_name(runs, "tool_accuracy")
    if not _has_score_by_name(runs, "tool_accuracy"):
        tool_accuracy_avg = _avg_score_by_name(runs, "accuracy")
    tool_accuracy = tool_accuracy_avg * 100
    if _has_score_by_name(runs, "hallucination"):
        hallucination_rate = round(_avg_score_by_name(runs, "hallucination") * 100, 2)
    else:
        safety_avg = _avg_score_by_name(runs, "safety")
        if not _has_score_by_name(runs, "safety"):
            # If no safety score is present, use accuracy as a weak proxy.
            safety_avg = _avg_score_by_name(runs, "accuracy")
        hallucination_rate = round((1 - safety_avg) * 100, 2) if safety_avg else 0.0

    # HITL: runs that have at least one human-attached score (no evaluator name)
    hitl_count = sum(
        1 for r in runs
        if any(s.comment is None or "judge" not in (s.comment or "").lower() for s in r.scores)
    )

    # $/task from Langfuse traces
    traces = _langfuse_traces(limit=50)
    costs = [t.get("total_cost") or t.get("totalCost") or 0.0 for t in traces]
    costs = [c for c in costs if c and c > 0]
    avg_cost = round(sum(costs) / len(costs), 4) if costs else 0.0

    return {
        "tsr": tsr,
        "tool_accuracy": round(tool_accuracy, 1),
        "hallucination_rate": hallucination_rate,
        "hitl_count": hitl_count,
        "p95_latency_ms": p95_latency,
        "avg_latency_ms": avg_latency,
        "avg_cost_per_task": avg_cost,
        "total_runs": total,
        "completed_runs": completed,
        "failed_runs": failed,
    }


# ─────────────────────────────────────────────────────────────
# Latency percentiles (time series for P50/P95/P99 chart)
# ─────────────────────────────────────────────────────────────

@router.get("/latency-percentiles", summary="Rolling P50/P95/P99 latency time series")
def get_latency_percentiles(points: int = Query(30, le=100)) -> list[dict]:
    runs = _get_runs()
    runs_with_latency = [r for r in runs if r.latency_ms > 0]

    if not runs_with_latency:
        return []

    # Sort by creation time, take last `points` batches
    runs_sorted = sorted(runs_with_latency, key=lambda r: r.created_at)
    chunk_size = max(1, len(runs_sorted) // points)

    result = []
    for i in range(0, len(runs_sorted), chunk_size):
        chunk = runs_sorted[i: i + chunk_size]
        lats = [r.latency_ms for r in chunk]
        ts = chunk[-1].created_at.strftime("%H:%M")
        result.append({
            "time": ts,
            "p50": _percentile(lats, 50),
            "p95": _percentile(lats, 95),
            "p99": _percentile(lats, 99),
        })

    return result[-points:]


# ─────────────────────────────────────────────────────────────
# Latency breakdown per agent (stacked: prompt / tool / synthesis / output)
# ─────────────────────────────────────────────────────────────

@router.get("/latency-breakdown", summary="Per-agent latency breakdown by stage")
def get_latency_breakdown() -> list[dict]:
    runs = _get_runs()
    by_agent: dict[str, list[float]] = defaultdict(list)

    for r in runs:
        if r.latency_ms > 0:
            by_agent[r.agent_name].append(r.latency_ms)

    result = []
    for agent_name, lats in by_agent.items():
        avg = statistics.mean(lats)
        # Approximate stage breakdown (no per-span data from OTEL in simple tracker)
        # Weights derived from typical LLM agent patterns
        result.append({
            "agent": agent_name,
            "prompt": round(avg * 0.15, 1),
            "tool_call": round(avg * 0.45, 1),
            "synthesis": round(avg * 0.25, 1),
            "output": round(avg * 0.15, 1),
            "total": round(avg, 1),
        })

    return result


# ─────────────────────────────────────────────────────────────
# Token throughput + cost per task (combo chart)
# ─────────────────────────────────────────────────────────────

@router.get("/token-cost", summary="Token throughput and cost per task over time")
def get_token_cost(points: int = Query(30, le=100)) -> list[dict]:
    traces = _langfuse_traces(limit=points)

    # Build a run-metadata lookup for token fallback (keyed by trace_id)
    runs = _get_runs()
    run_token_map: dict[str, int] = {}
    for r in runs:
        total = (
            int(r.metadata.get("total_tokens") or 0)
            or int(r.metadata.get("input_tokens") or 0) + int(r.metadata.get("output_tokens") or 0)
        )
        if total > 0:
            run_token_map[r.trace_id] = total

    result = []
    for i, t in enumerate(reversed(traces)):
        # Langfuse v3 trace list does not include per-trace usage totals;
        # fall back to tokens stored in the control plane run metadata.
        usage = t.get("usage") or {}
        total_tokens = (
            int(usage.get("input") or 0) + int(usage.get("output") or 0)
            or int(usage.get("total") or 0)
        )
        if total_tokens == 0:
            trace_id = _extract_trace_id(t) or ""
            total_tokens = run_token_map.get(trace_id, 0)

        cost = t.get("total_cost") or t.get("totalCost") or 0.0
        ts = t.get("timestamp") or t.get("created_at") or ""
        if ts:
            try:
                ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).strftime("%H:%M")
            except Exception:
                ts = str(i)
        else:
            ts = str(i)

        result.append({
            "time": ts,
            "tokens": total_tokens,
            "cost": round(float(cost), 4),
        })

    return result


# ─────────────────────────────────────────────────────────────
# Error recovery rate per agent
# ─────────────────────────────────────────────────────────────

@router.get("/error-recovery", summary="Error recovery rate by agent")
def get_error_recovery() -> list[dict]:
    from sdk.schemas import RunStatus
    runs = _get_runs()

    by_agent: dict[str, dict] = defaultdict(lambda: {"total": 0, "failed": 0, "recovered": 0})
    for r in runs:
        by_agent[r.agent_name]["total"] += 1
        if r.status == RunStatus.FAILED:
            by_agent[r.agent_name]["failed"] += 1
        elif r.status == RunStatus.COMPLETED and r.error:
            # Had an error but ultimately completed = recovered
            by_agent[r.agent_name]["recovered"] += 1

    result = []
    for agent, counts in by_agent.items():
        total = counts["total"]
        failed = counts["failed"]
        recovered = counts["recovered"]
        retries = failed + recovered
        recovery_rate = round((recovered / retries * 100) if retries else 100.0, 1)
        result.append({
            "agent": agent,
            "recovery_rate": recovery_rate,
            "total_retries": retries,
            "session_crashes": failed,
        })

    return result


# ─────────────────────────────────────────────────────────────
# Tool accuracy per tool name
# ─────────────────────────────────────────────────────────────

@router.get("/tool-accuracy", summary="Tool selection accuracy by tool name")
def get_tool_accuracy() -> list[dict]:
    runs = _get_runs()

    # Aggregate accuracy scores per agent as proxy for tool accuracy
    by_agent: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        for s in r.scores:
            if _score_name_matches(s.name, "accuracy") or _score_name_matches(s.name, "tool_accuracy"):
                by_agent[r.agent_name].append(s.value)

    if not by_agent:
        # Fallback: return mock tool names with reasonable defaults
        return [
            {"tool": agent, "accuracy": round(statistics.mean(vals) * 100, 1)}
            for agent, vals in by_agent.items()
        ]

    return [
        {
            "tool": agent,
            "accuracy": round(statistics.mean(vals) * 100, 1),
        }
        for agent, vals in by_agent.items()
    ]


# ─────────────────────────────────────────────────────────────
# TSR (Task Success Rate) by agent/workflow
# ─────────────────────────────────────────────────────────────

@router.get("/tsr-by-agent", summary="Task success rate broken down by agent")
def get_tsr_by_agent() -> list[dict]:
    from sdk.schemas import RunStatus
    runs = _get_runs()

    by_agent: dict[str, dict] = defaultdict(lambda: {"total": 0, "completed": 0})
    for r in runs:
        by_agent[r.agent_name]["total"] += 1
        if r.status == RunStatus.COMPLETED:
            by_agent[r.agent_name]["completed"] += 1

    result = []
    for agent, counts in by_agent.items():
        tsr = round(counts["completed"] / counts["total"] * 100, 1) if counts["total"] else 0.0
        result.append({"agent": agent, "tsr": tsr, "total": counts["total"]})

    return sorted(result, key=lambda x: x["tsr"], reverse=True)


# ─────────────────────────────────────────────────────────────
# Scores trend over time
# ─────────────────────────────────────────────────────────────

@router.get("/scores-trend", summary="Evaluation score trends over time")
def get_scores_trend(points: int = Query(30, le=100)) -> list[dict]:
    runs = _get_runs()
    runs_sorted = sorted(
        [r for r in runs if r.scores],
        key=lambda r: r.created_at,
    )

    result = []
    chunk_size = max(1, len(runs_sorted) // max(points, 1))

    for i in range(0, len(runs_sorted), chunk_size):
        chunk = runs_sorted[i: i + chunk_size]
        # Include seconds to avoid multiple runs collapsing into the same x-axis
        # bucket and rendering visually confusing vertical jumps.
        ts = chunk[-1].created_at.strftime("%m/%d %H:%M:%S")

        # Aggregate by (agent, score_name) so mixed-agent runs do not produce
        # ambiguous blended lines.
        score_totals: dict[str, list[float]] = defaultdict(list)
        for r in chunk:
            for s in r.scores:
                key = f"{r.agent_name}::{s.name}"
                score_totals[key].append(s.value)

        point: dict[str, Any] = {"time": ts}
        for name, vals in score_totals.items():
            point[name] = round(statistics.mean(vals), 3)

        result.append(point)

    return result[-points:]


# ─────────────────────────────────────────────────────────────
# Hallucination rate per agent (from safety / accuracy scores)
# ─────────────────────────────────────────────────────────────

@router.get("/hallucination-rate", summary="Hallucination rate proxy per agent")
def get_hallucination_rate() -> list[dict]:
    runs = _get_runs()
    by_agent: dict[str, list[float]] = defaultdict(list)

    for r in runs:
        for s in r.scores:
            if _score_name_matches(s.name, "hallucination"):
                by_agent[r.agent_name].append(s.value)
            elif _score_name_matches(s.name, "safety") or _score_name_matches(s.name, "accuracy"):
                # hallucination = inverse of safety/accuracy
                hallu = 1.0 - s.value
                by_agent[r.agent_name].append(hallu)

    result = []
    for agent, vals in by_agent.items():
        rate = round(statistics.mean(vals) * 100, 2)
        result.append({"agent": agent, "hallucination_rate": rate})

    return result


@router.get("/hallucination-trend", summary="Rolling hallucination rate trend")
def get_hallucination_trend(points: int = Query(30, le=100)) -> list[dict]:
    runs = _get_runs()
    runs_sorted = sorted(
        [
            r
            for r in runs
            if any(
                _score_name_matches(s.name, "safety")
                or _score_name_matches(s.name, "accuracy")
                for s in r.scores
            )
        ],
        key=lambda r: r.created_at,
    )

    result = []
    chunk_size = max(1, len(runs_sorted) // max(points, 1))

    for i in range(0, len(runs_sorted), chunk_size):
        chunk = runs_sorted[i: i + chunk_size]
        ts = chunk[-1].created_at.strftime("%H:%M")
        vals = []
        for r in chunk:
            for s in r.scores:
                if _score_name_matches(s.name, "safety") or _score_name_matches(s.name, "accuracy"):
                    vals.append((1.0 - s.value) * 100)
        rate = round(statistics.mean(vals), 2) if vals else 0.0
        result.append({"time": ts, "rate": rate})

    return result[-points:]


# ─────────────────────────────────────────────────────────────
# Decision turn count (loop detection)
# ─────────────────────────────────────────────────────────────

@router.get("/decision-turns", summary="Decision turn count per run (loop detection)")
def get_decision_turns() -> list[dict]:
    runs = _get_runs()

    by_agent: dict[str, list[int]] = defaultdict(list)
    for r in runs:
        turns = r.metadata.get("turns") or r.metadata.get("decision_turns") or 1
        by_agent[r.agent_name].append(int(turns))

    result = []
    for agent, turn_counts in by_agent.items():
        avg_turns = round(statistics.mean(turn_counts), 1)
        loops_detected = sum(1 for t in turn_counts if t > 12)
        result.append({
            "agent": agent,
            "avg_turns": avg_turns,
            "loops_detected": loops_detected,
            "total_runs": len(turn_counts),
        })

    return result


# ─────────────────────────────────────────────────────────────
# Registered agents (for dropdowns / overview)
# ─────────────────────────────────────────────────────────────

@router.get("/agents-summary", summary="Summary of registered agents")
def get_agents_summary() -> list[dict]:
    from control_plane.registry import registry
    from sdk.schemas import RunStatus
    runs = _get_runs()

    run_counts: dict[str, dict] = defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0})
    latencies: dict[str, list[float]] = defaultdict(list)
    trace_costs = _trace_cost_map(limit=500)
    costs_by_agent: dict[str, list[float]] = defaultdict(list)
    for r in runs:
        run_counts[r.agent_name]["total"] += 1
        if r.status == RunStatus.COMPLETED:
            run_counts[r.agent_name]["completed"] += 1
        elif r.status == RunStatus.FAILED:
            run_counts[r.agent_name]["failed"] += 1
        if r.latency_ms > 0:
            latencies[r.agent_name].append(r.latency_ms)
        run_cost = trace_costs.get(r.trace_id, 0.0)
        if run_cost > 0:
            costs_by_agent[r.agent_name].append(run_cost)

    agents = registry.list_all()
    if not agents:
        # Fallback: infer agent list from Langfuse traces when registry is empty.
        traces = _langfuse_traces(limit=500)
        inferred_names = sorted(
            {
                _extract_agent_name_from_trace(t)
                for t in traces
                if _extract_agent_name_from_trace(t)
            }
        )
        agents = [
            {
                "name": name,
                "description": "",
                "framework": "langchain",
                "version": "1.0.0",
            }
            for name in inferred_names
        ]
    result = []
    for a in agents:
        name = a.get("name", "")
        counts = run_counts.get(name, {"total": 0, "completed": 0, "failed": 0})
        lats = latencies.get(name, [])
        costs = costs_by_agent.get(name, [])
        result.append({
            "name": name,
            "description": a.get("description", ""),
            "framework": a.get("framework", "generic"),
            "version": a.get("version", "1.0.0"),
            "total_runs": counts["total"],
            "completed_runs": counts["completed"],
            "failed_runs": counts["failed"],
            "tsr": round(counts["completed"] / counts["total"] * 100, 1) if counts["total"] else 0.0,
            "avg_latency_ms": round(statistics.mean(lats), 1) if lats else 0.0,
            "p95_latency_ms": _percentile(lats, 95),
            "avg_cost_per_task": round(statistics.mean(costs), 4) if costs else 0.0,
        })

    return result


@router.get("/agent-traces", summary="Recent traces for a selected agent")
def get_agent_traces(
    agent_name: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=200),
) -> list[dict]:
    normalized_agent = agent_name.strip().lower()
    runs = _get_runs()
    runs_for_agent = [
        r
        for r in runs
        if r.trace_id and str(r.agent_name).strip().lower() == normalized_agent
    ]
    # Keep only latest run per trace_id to avoid duplicates.
    latest_run_by_trace: dict[str, Any] = {}
    for run in sorted(runs_for_agent, key=lambda r: r.created_at):
        latest_run_by_trace[run.trace_id] = run

    trace_ids = set(latest_run_by_trace.keys())
    traces = _langfuse_traces(limit=500)

    result: list[dict] = []
    for trace in traces:
        trace_id = _extract_trace_id(trace)
        if not trace_id:
            continue

        inferred_agent = _extract_agent_name_from_trace(trace).strip().lower()
        matches_run_trace = trace_id in trace_ids if trace_ids else False
        matches_inferred_agent = inferred_agent == normalized_agent if inferred_agent else False
        if not (matches_run_trace or matches_inferred_agent):
            continue

        run = latest_run_by_trace.get(trace_id)
        input_value = trace.get("input")
        output_value = trace.get("output")
        resolved_agent_name = (
            (run.agent_name if run else "")
            or _extract_agent_name_from_trace(trace)
            or agent_name
        )

        run_status = ""
        if run is not None:
            status_value = getattr(run.status, "value", None)
            run_status = str(status_value or run.status or "")

        result.append(
            {
                "trace_id": trace_id,
                "agent_name": resolved_agent_name,
                "run_id": run.run_id if run else "",
                "status": run_status,
                "timestamp": _extract_trace_timestamp(trace),
                "latency_ms": round(_extract_trace_latency_ms(trace), 2),
                "cost": round(_extract_trace_cost(trace), 6),
                "turns": int((run.metadata.get("turns") or run.metadata.get("decision_turns") or 0)) if run else _extract_trace_turns(trace),
                "session_id": trace.get("session_id") or trace.get("sessionId") or "",
                "user_id": trace.get("user_id") or trace.get("userId") or "",
                "input_preview": _preview_value(input_value),
                "output_preview": _preview_value(output_value),
            }
        )

    # Sort latest first and respect user limit.
    result.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    if result:
        return result[:limit]

    # Fallback: if Langfuse traces are not linked yet, return run-level records
    # so the UI still shows recent activity for this agent.
    fallback_rows: list[dict] = []
    for run in sorted(runs_for_agent, key=lambda r: r.created_at, reverse=True):
        matched_trace = _nearest_trace_for_run(run, traces, max_delta_seconds=900)
        mapped_trace_id = _extract_trace_id(matched_trace) if matched_trace else None
        status_value = getattr(run.status, "value", None)
        run_status = str(status_value or run.status or "")
        fallback_rows.append(
            {
                "trace_id": mapped_trace_id or run.trace_id,
                "run_trace_id": run.trace_id,
                "agent_name": run.agent_name,
                "run_id": run.run_id,
                "status": run_status,
                "timestamp": run.created_at.isoformat(),
                "latency_ms": round(float(run.latency_ms or 0.0), 2),
                "cost": 0.0,
                "turns": int(run.metadata.get("turns") or run.metadata.get("decision_turns") or 0),
                "session_id": "",
                "user_id": "",
                "input_preview": _preview_value(run.input),
                "output_preview": _preview_value(run.output),
            }
        )
    return fallback_rows[:limit]


@router.get("/agent-traces/{trace_id}", summary="Full detail for a trace")
def get_agent_trace_detail(trace_id: str) -> dict:
    from control_plane.langfuse_client import get_scores, get_trace

    def _build_langfuse_detail(trace_obj: dict, requested: str | None = None) -> dict:
        actual_trace_id = _extract_trace_id(trace_obj) or requested_id
        observations = _normalize_observations(trace_obj.get("observations"))
        turns = _extract_trace_turns(trace_obj)
        if turns <= 0 and observations:
            turns = _estimate_turns_from_observations(observations)
        detail = {
            "source": "langfuse",
            "trace_id": actual_trace_id,
            "timestamp": _extract_trace_timestamp(trace_obj),
            "latency_ms": round(_extract_trace_latency_ms(trace_obj), 2),
            "cost": round(_extract_trace_cost(trace_obj), 6),
            "turns": turns,
            "session_id": trace_obj.get("session_id") or trace_obj.get("sessionId") or "",
            "user_id": trace_obj.get("user_id") or trace_obj.get("userId") or "",
            "name": trace_obj.get("name") or "",
            "input": trace_obj.get("input"),
            "output": trace_obj.get("output"),
            "metadata": trace_obj.get("metadata") or {},
            "scores": get_scores(actual_trace_id),
            "observations": observations,
            "raw_trace": trace_obj,
        }
        if requested and requested != actual_trace_id:
            detail["mapped_from_trace_id"] = requested
        return detail

    requested_id = _normalize_trace_id(trace_id)
    trace = get_trace(requested_id)
    if trace is not None:
        return _build_langfuse_detail(trace)

    # Fallback to in-memory run if Langfuse detail is unavailable.
    runs = _get_runs()
    for run in runs:
        if _normalize_trace_id(run.trace_id) == requested_id or run.trace_id == trace_id:
            # Best-effort mapping when run trace_id isn't the Langfuse id:
            # 1) nearest Langfuse trace for same agent around the run timestamp
            # 2) if none, nearest trace by timestamp regardless of agent tag
            traces = _langfuse_traces(limit=300)
            nearest = _nearest_trace_for_run(run, traces, max_delta_seconds=900)
            if nearest is not None:
                mapped_id = _extract_trace_id(nearest)
                if mapped_id:
                    mapped_trace = get_trace(_normalize_trace_id(mapped_id))
                    if mapped_trace is not None:
                        return _build_langfuse_detail(mapped_trace, requested=trace_id)

            status_value = getattr(run.status, "value", None)
            run_status = str(status_value or run.status or "")
            return {
                "source": "run_tracker",
                "trace_id": run.trace_id,
                "run_id": run.run_id,
                "timestamp": run.created_at.isoformat(),
                "latency_ms": round(float(run.latency_ms or 0.0), 2),
                "cost": 0.0,
                "turns": int(run.metadata.get("turns") or run.metadata.get("decision_turns") or 0),
                "status": run_status,
                "input": run.input,
                "output": run.output,
                "metadata": run.metadata or {},
                "scores": [s.model_dump(mode="json") for s in run.scores],
                "observations": [],
            }

    return {"source": "none", "trace_id": trace_id, "error": "Trace not found"}
