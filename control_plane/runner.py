"""Run tracker — stores in-memory run state and dispatches eval jobs."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from threading import Lock
from typing import Any

from sdk.schemas import AgentRunReport, RunRecord, RunStatus


class RunTracker:
    """
    Thread-safe in-memory store for agent run records.

    Runs are kept in memory for the lifetime of the process. For production
    deployments consider persisting records to a database.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._lock = Lock()

    def create(self, report: AgentRunReport) -> RunRecord:
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            agent_name=report.agent_name,
            trace_id=report.trace_id,
            status=report.status,
            input=report.input,
            output=report.output,
            latency_ms=report.latency_ms,
            error=report.error,
            metadata=report.metadata,
        )
        with self._lock:
            self._runs[run_id] = record
        return record

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def update_status(
        self,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
    ) -> RunRecord | None:
        with self._lock:
            record = self._runs.get(run_id)
            if record:
                record.status = status
                record.error = error
                record.updated_at = datetime.utcnow()
        return record

    def list_all(
        self,
        agent_name: str | None = None,
        status: RunStatus | None = None,
        limit: int = 100,
    ) -> list[RunRecord]:
        with self._lock:
            runs = list(self._runs.values())

        if agent_name:
            runs = [r for r in runs if r.agent_name == agent_name]
        if status:
            runs = [r for r in runs if r.status == status]

        runs.sort(key=lambda r: r.created_at, reverse=True)
        return runs[:limit]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            runs = list(self._runs.values())

        total = len(runs)
        if total == 0:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "running": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
            }

        completed = sum(1 for r in runs if r.status == RunStatus.COMPLETED)
        failed = sum(1 for r in runs if r.status == RunStatus.FAILED)
        running = sum(1 for r in runs if r.status == RunStatus.RUNNING)
        latencies = [r.latency_ms for r in runs if r.latency_ms > 0]

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "success_rate": round(completed / total, 3) if total else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 1)
            if latencies
            else 0.0,
        }


async def dispatch_evals(
    run_record: RunRecord,
    evaluator_names: list[str],
    llm_judge_config: dict | None = None,
) -> None:
    """
    Fire-and-forget coroutine: run each named evaluator against the
    completed run record and push scores to Langfuse.

    llm_judge_config — if provided, overrides platform defaults for this
    specific agent (sourced from AgentRegistration.llm_judge_config).
    """
    from control_plane.evals.llm_judge import LLMJudge
    from control_plane.evals.rule_based import RuleBasedEvaluator
    from control_plane.langfuse_client import push_score

    cfg = llm_judge_config or {}
    evaluator_map = {
        "llm_judge": LLMJudge(
            model=cfg.get("model"),
            dimensions=cfg.get("dimensions"),
            prompt_template=cfg.get("prompt_template"),
            temperature=cfg.get("temperature"),
        ),
        "rule_based": RuleBasedEvaluator(),
    }

    for name in evaluator_names:
        evaluator = evaluator_map.get(name)
        if evaluator is None:
            continue
        try:
            scores = await evaluator.evaluate(
                trace_id=run_record.trace_id,
                output=str(run_record.output or ""),
                input=str(run_record.input or ""),
            )
            for score in scores:
                push_score(
                    trace_id=run_record.trace_id,
                    name=score.name,
                    value=score.value,
                    comment=score.comment,
                )
                run_record.scores.append(score)
        except Exception:
            pass


# Module-level singleton
tracker = RunTracker()
