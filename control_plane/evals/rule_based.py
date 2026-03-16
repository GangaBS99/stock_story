"""
Rule-based evaluator.

Applies deterministic checks to the agent output:
- length_ok    (1.0/0.0): Output has at least 20 characters
- not_empty    (1.0/0.0): Output is not empty / whitespace-only
- no_error_msg (1.0/0.0): Output does not contain common error patterns
- json_valid   (1.0/0.0): Output is valid JSON (if it looks like JSON)

Scores are always 0 or 1 (binary pass/fail).
"""
from __future__ import annotations

import json
import re

from control_plane.evals.base import AbstractEvaluator
from sdk.schemas import Score


ERROR_PATTERNS = re.compile(
    r"(traceback|exception|error:|typeerror|valueerror|keyerror|attributeerror)",
    re.IGNORECASE,
)


class RuleBasedEvaluator(AbstractEvaluator):
    """Deterministic rule-based scorer — no external API calls."""

    @property
    def name(self) -> str:
        return "rule_based"

    async def evaluate(
        self,
        trace_id: str,
        output: str,
        input: str = "",
    ) -> list[Score]:
        scores: list[Score] = []

        # not_empty
        not_empty = bool(output.strip())
        scores.append(
            Score(
                name="rule.not_empty",
                value=1.0 if not_empty else 0.0,
                comment="Output is non-empty" if not_empty else "Output is empty",
                trace_id=trace_id,
            )
        )

        # length_ok (>=20 characters)
        length_ok = len(output.strip()) >= 20
        scores.append(
            Score(
                name="rule.length_ok",
                value=1.0 if length_ok else 0.0,
                comment=f"Output length: {len(output)} chars",
                trace_id=trace_id,
            )
        )

        # no_error_msg
        has_error = bool(ERROR_PATTERNS.search(output))
        scores.append(
            Score(
                name="rule.no_error_msg",
                value=0.0 if has_error else 1.0,
                comment="Error pattern detected" if has_error else "No error pattern",
                trace_id=trace_id,
            )
        )

        # json_valid (only checked if output looks like JSON)
        stripped = output.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                json_valid = True
            except json.JSONDecodeError:
                json_valid = False
            scores.append(
                Score(
                    name="rule.json_valid",
                    value=1.0 if json_valid else 0.0,
                    comment="Valid JSON" if json_valid else "Invalid JSON",
                    trace_id=trace_id,
                )
            )

        return scores
