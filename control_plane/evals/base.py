"""Abstract evaluator protocol — all evaluators must implement this."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sdk.schemas import Score


class AbstractEvaluator(ABC):
    """
    Base class for all evaluators.

    evaluate() receives the Langfuse trace_id, the raw output text, and the
    original input. It returns a list of Score objects. The runner then pushes
    those scores to Langfuse via langfuse.score().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique evaluator identifier (matches the name used in evaluators list)."""

    @abstractmethod
    async def evaluate(
        self,
        trace_id: str,
        output: str,
        input: str = "",
    ) -> list[Score]:
        """
        Evaluate a completed agent run.

        Args:
            trace_id: Langfuse trace identifier for this run.
            output:   The agent's text output to evaluate.
            input:    The original input given to the agent (may be used for
                      relevance / faithfulness scoring).

        Returns:
            List of Score objects (name, value 0-1, optional comment).
        """
