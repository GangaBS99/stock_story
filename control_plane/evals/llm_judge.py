"""
LLM-as-judge evaluator — fully configurable.

Configuration (in order of precedence):
  1. Constructor arguments  — per-instance, highest priority
  2. .env / environment     — platform-wide defaults
  3. Built-in defaults      — fallback

Environment variables:
  JUDGE_MODEL          OpenAI model to use            (default: gpt-4o-mini)
  JUDGE_TEMPERATURE    Sampling temperature            (default: 0)
  JUDGE_DIMENSIONS     Comma-separated dimension names (default: quality,relevance)
  JUDGE_PROMPT         Full custom prompt template     (default: built-in)
                       Must contain {input}, {output}, and one {dims_json} placeholder.
"""
from __future__ import annotations

import json
import os
import textwrap
from dataclasses import dataclass, field
from typing import Any

from control_plane.evals.base import AbstractEvaluator
from sdk.schemas import Score

# ── built-in prompt ───────────────────────────────────────────────────────────

_DEFAULT_PROMPT = """\
You are an impartial evaluator for AI agent outputs.

INPUT:
{input}

OUTPUT:
{output}

Rate the output on EACH of the following dimensions.
Return ONLY valid JSON — a single object whose keys are exactly the dimension
names listed below, each mapped to an object with "score" (float 0.0-1.0) and
"comment" (one sentence):

Dimensions to score:
{dims_json}

Example format:
{{
  "quality":   {{"score": 0.9, "comment": "Clear and well-structured."}},
  "relevance": {{"score": 0.8, "comment": "Directly addresses the question."}}
}}
"""


# ── dimension definition ──────────────────────────────────────────────────────

@dataclass
class Dimension:
    """A single scoring dimension for the LLM judge."""
    name: str
    description: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "description": self.description}


# Built-in dimensions
DEFAULT_DIMENSIONS: list[Dimension] = [
    Dimension("quality",   "Clarity, coherence, and usefulness of the response"),
    Dimension("relevance", "How directly the response addresses the input"),
]

# All available named dimensions (add your own here)
DIMENSION_LIBRARY: dict[str, Dimension] = {
    "quality":     Dimension("quality",     "Clarity, coherence, and usefulness of the response"),
    "relevance":   Dimension("relevance",   "How directly the response addresses the input"),
    "accuracy":    Dimension("accuracy",    "Factual correctness of the response"),
    "conciseness": Dimension("conciseness", "Whether the response is appropriately brief"),
    "safety":      Dimension("safety",      "Absence of harmful, biased, or offensive content"),
    "helpfulness": Dimension("helpfulness", "How useful the response is to the user"),
    "tone":        Dimension("tone",        "Appropriate and professional tone"),
}


# ── evaluator ─────────────────────────────────────────────────────────────────

class LLMJudge(AbstractEvaluator):
    """
    Configurable LLM-as-judge evaluator.

    Usage (with defaults from .env)::

        judge = LLMJudge()

    Usage (custom per-instance config)::

        judge = LLMJudge(
            model="gpt-4o",
            dimensions=["accuracy", "safety", "helpfulness"],
            prompt_template="Your custom prompt with {input}, {output}, {dims_json}",
            temperature=0.2,
        )
    """

    def __init__(
        self,
        model: str | None = None,
        dimensions: list[str] | None = None,
        prompt_template: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self._model = model or os.getenv("JUDGE_MODEL", "gpt-4o-mini")
        self._temperature = (
            temperature
            if temperature is not None
            else float(os.getenv("JUDGE_TEMPERATURE", "0"))
        )
        self._prompt_template = (
            prompt_template
            or os.getenv("JUDGE_PROMPT")
            or _DEFAULT_PROMPT
        )

        # Resolve dimensions
        raw_dims = dimensions or _parse_env_dimensions()
        self._dimensions: list[Dimension] = [
            DIMENSION_LIBRARY.get(d, Dimension(d, "")) for d in raw_dims
        ]

    @property
    def name(self) -> str:
        return "llm_judge"

    def _build_prompt(self, input: str, output: str) -> str:
        dims_json = json.dumps(
            [d.to_dict() for d in self._dimensions], indent=2
        )
        return self._prompt_template.format(
            input=input[:2000],
            output=output[:4000],
            dims_json=dims_json,
        )

    async def evaluate(
        self,
        trace_id: str,
        output: str,
        input: str = "",
    ) -> list[Score]:
        if not output.strip():
            return []

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "user", "content": self._build_prompt(input, output)}
                ],
                response_format={"type": "json_object"},
                temperature=self._temperature,
            )

            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)

            scores: list[Score] = []
            for dim in self._dimensions:
                entry = data.get(dim.name, {})
                if isinstance(entry, dict):
                    val = float(entry.get("score", 0.0))
                    comment = entry.get("comment")
                else:
                    # Fallback: some models return a plain float
                    val = float(entry) if entry else 0.0
                    comment = None

                scores.append(
                    Score(
                        name=f"llm_judge.{dim.name}",
                        value=max(0.0, min(1.0, val)),
                        comment=comment,
                        trace_id=trace_id,
                    )
                )

            return scores

        except Exception as exc:
            return [
                Score(
                    name="llm_judge.error",
                    value=0.0,
                    comment=str(exc),
                    trace_id=trace_id,
                )
            ]


def _parse_env_dimensions() -> list[str]:
    """Read JUDGE_DIMENSIONS env var (comma-separated) or return defaults."""
    raw = os.getenv("JUDGE_DIMENSIONS", "")
    if raw.strip():
        return [d.strip() for d in raw.split(",") if d.strip()]
    return [d.name for d in DEFAULT_DIMENSIONS]
