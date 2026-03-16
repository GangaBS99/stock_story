from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from control_plane.evals.llm_judge import DIMENSION_LIBRARY, LLMJudge
from control_plane.evals.rule_based import RuleBasedEvaluator
from control_plane.langfuse_client import push_score
from sdk.schemas import LLMJudgeConfig

router = APIRouter(prefix="/evals", tags=["evals"])

# Default (platform-wide) instances — config driven by .env
_default_evaluators = {
    "llm_judge": LLMJudge(),
    "rule_based": RuleBasedEvaluator(),
}


class EvalRequest(BaseModel):
    trace_id: str
    output: str
    input: str = ""
    evaluators: list[str] = ["llm_judge", "rule_based"]
    llm_judge_config: LLMJudgeConfig | None = None


@router.post("/run", summary="Run evaluators against a trace and push scores to Langfuse")
async def run_evals(req: EvalRequest) -> dict:
    results: dict[str, list[dict]] = {}

    for eval_name in req.evaluators:
        if eval_name not in _default_evaluators:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown evaluator '{eval_name}'. Available: {list(_default_evaluators)}",
            )

        # Build a custom LLMJudge instance if per-request config was supplied
        if eval_name == "llm_judge" and req.llm_judge_config:
            cfg = req.llm_judge_config
            evaluator = LLMJudge(
                model=cfg.model,
                dimensions=cfg.dimensions,
                prompt_template=cfg.prompt_template,
                temperature=cfg.temperature,
            )
        else:
            evaluator = _default_evaluators[eval_name]

        scores = await evaluator.evaluate(
            trace_id=req.trace_id,
            output=req.output,
            input=req.input,
        )
        for score in scores:
            push_score(
                trace_id=req.trace_id,
                name=score.name,
                value=score.value,
                comment=score.comment,
            )
        results[eval_name] = [s.model_dump() for s in scores]

    return {"trace_id": req.trace_id, "scores": results}


@router.get("/available", summary="List available evaluator names")
def list_evaluators() -> list[str]:
    return list(_default_evaluators.keys())


@router.get("/dimensions", summary="List all available judge dimensions")
def list_dimensions() -> list[dict]:
    return [
        {"name": d.name, "description": d.description}
        for d in DIMENSION_LIBRARY.values()
    ]
