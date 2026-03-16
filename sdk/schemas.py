from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Framework(str, Enum):
    PYDANTIC_AI = "pydantic_ai"
    LANGCHAIN = "langchain"
    OPENAI = "openai"
    GENERIC = "generic"


class LLMJudgeConfig(BaseModel):
    """Per-agent LLM judge configuration stored at registration time."""

    model: str | None = Field(None, description="OpenAI model (e.g. gpt-4o, gpt-4o-mini)")
    dimensions: list[str] | None = Field(
        None,
        description=(
            "Scoring dimensions for this agent. "
            "Available: quality, relevance, accuracy, conciseness, safety, helpfulness, tone"
        ),
    )
    prompt_template: str | None = Field(
        None,
        description=(
            "Custom judge prompt. Must contain {input}, {output}, {dims_json} placeholders. "
            "Leave None to use the platform default."
        ),
    )
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="Sampling temperature (0 = deterministic)")


class AgentRegistration(BaseModel):
    name: str = Field(..., description="Unique agent identifier")
    description: str = Field("", description="What the agent does")
    framework: Framework = Field(Framework.GENERIC, description="Underlying framework")
    version: str = Field("1.0.0", description="Agent version string")
    evaluators: list[str] = Field(
        default_factory=list,
        description="Evaluator names to run after each run (e.g. llm_judge, rule_based)",
    )
    llm_judge_config: LLMJudgeConfig | None = Field(
        None,
        description="Per-agent LLM judge settings. Overrides platform .env defaults.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentRunReport(BaseModel):
    agent_name: str = Field(..., description="Name of the registered agent")
    trace_id: str = Field(..., description="Langfuse trace ID for this run")
    input: Any = Field(..., description="Raw input passed to the agent")
    output: Any = Field(None, description="Raw output produced by the agent")
    status: RunStatus = Field(RunStatus.COMPLETED)
    latency_ms: float = Field(0.0, description="Wall-clock latency in milliseconds")
    error: str | None = Field(None, description="Error message if status is FAILED")
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)


class Score(BaseModel):
    name: str
    value: float = Field(..., ge=0.0, le=1.0)
    comment: str | None = None
    trace_id: str | None = None


class RunRecord(BaseModel):
    run_id: str
    agent_name: str
    trace_id: str
    status: RunStatus
    input: Any
    output: Any = None
    latency_ms: float = 0.0
    error: str | None = None
    scores: list[Score] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
