"""
Dashboard aggregation endpoints.

All data is sourced from the in-memory RunTracker and the Langfuse SDK.
The React frontend polls these endpoints every 10 seconds.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
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


def _avg_score_by_name(runs, score_name: str) -> float:
    values = []
    for r in runs:
        for s in r.scores:
            if s.name == score_name:
                values.append(s.value)
    return round(statistics.mean(values), 3) if values else 0.0


def _langfuse_traces(limit: int = 100) -> list[dict]:
    try:
        from control_plane.langfuse_client import get_traces
        return get_traces(limit=limit)
    except Exception:
        return []


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

    tool_accuracy = _avg_score_by_name(runs, "accuracy") * 100
    safety_avg = _avg_score_by_name(runs, "safety")
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
    result = []

    for i, t in enumerate(reversed(traces)):
        usage = t.get("usage") or {}
        total_tokens = (
            (usage.get("input") or 0)
            + (usage.get("output") or 0)
        )
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
            if s.name in ("accuracy", "tool_accuracy"):
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
        ts = chunk[-1].created_at.strftime("%m/%d %H:%M")

        # Aggregate all score names in this chunk
        score_totals: dict[str, list[float]] = defaultdict(list)
        for r in chunk:
            for s in r.scores:
                score_totals[s.name].append(s.value)

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
            if s.name in ("safety", "accuracy", "hallucination"):
                # hallucination = inverse of safety/accuracy
                hallu = 1.0 - s.value if s.name in ("safety", "accuracy") else s.value
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
        [r for r in runs if any(s.name in ("safety", "accuracy") for s in r.scores)],
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
                if s.name in ("safety", "accuracy"):
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
    for r in runs:
        run_counts[r.agent_name]["total"] += 1
        if r.status == RunStatus.COMPLETED:
            run_counts[r.agent_name]["completed"] += 1
        elif r.status == RunStatus.FAILED:
            run_counts[r.agent_name]["failed"] += 1
        if r.latency_ms > 0:
            latencies[r.agent_name].append(r.latency_ms)

    agents = registry.list_all()
    result = []
    for a in agents:
        name = a.get("name", "")
        counts = run_counts.get(name, {"total": 0, "completed": 0, "failed": 0})
        lats = latencies.get(name, [])
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
        })

    return result
