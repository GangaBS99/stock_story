from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from control_plane.registry import registry
from control_plane.runner import dispatch_evals, tracker
from sdk.schemas import AgentRunReport, RunRecord, RunStatus

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", summary="Report a completed agent run")
async def create_run(report: AgentRunReport) -> dict:
    record = tracker.create(report)

    # Look up evaluators + per-agent judge config from the registry
    agent_meta = registry.get(report.agent_name)
    evaluators = agent_meta.get("evaluators", []) if agent_meta else []
    llm_judge_config = agent_meta.get("llm_judge_config") if agent_meta else None

    if evaluators and report.status == RunStatus.COMPLETED:
        asyncio.create_task(dispatch_evals(record, evaluators, llm_judge_config))

    return {"run_id": record.run_id, "status": record.status}


@router.get("", summary="List runs with optional filters")
def list_runs(
    agent_name: str | None = Query(None),
    status: RunStatus | None = Query(None),
    limit: int = Query(100, le=500),
) -> list[dict]:
    runs = tracker.list_all(agent_name=agent_name, status=status, limit=limit)
    return [r.model_dump(mode="json") for r in runs]


@router.get("/stats", summary="Aggregate run statistics")
def run_stats() -> dict:
    return tracker.stats()


@router.get("/{run_id}", summary="Get a single run by ID")
def get_run(run_id: str) -> dict:
    record = tracker.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return record.model_dump(mode="json")


@router.post("/{run_id}/score", summary="Attach a human score to a run")
async def score_run(run_id: str, name: str, value: float, comment: str = "") -> dict:
    record = tracker.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    from control_plane.langfuse_client import push_score
    from sdk.schemas import Score

    score = Score(name=name, value=value, comment=comment, trace_id=record.trace_id)
    push_score(
        trace_id=record.trace_id,
        name=name,
        value=value,
        comment=comment or None,
    )
    record.scores.append(score)
    return {"status": "scored", "score": score.model_dump()}
