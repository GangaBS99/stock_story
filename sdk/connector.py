from __future__ import annotations

import asyncio
import functools
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable

import httpx

from sdk.schemas import AgentRegistration, AgentRunReport, Framework, LLMJudgeConfig, RunStatus


class BaseConnector(ABC):
    """
    Abstract base for all framework connectors.

    Subclasses implement _setup_tracing() to configure their framework's
    OTEL/callback instrumentation, and wrap their agent's run() method
    to call _report_run() so every execution is tracked by the control plane.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        framework: Framework = Framework.GENERIC,
        version: str = "1.0.0",
        evaluators: list[str] | None = None,
        llm_judge_config: LLMJudgeConfig | None = None,
        control_plane_url: str = "http://localhost:8500",
    ) -> None:
        self.name = name
        self.description = description
        self.framework = framework
        self.version = version
        self.evaluators = evaluators or []
        self.llm_judge_config = llm_judge_config
        self.control_plane_url = control_plane_url.rstrip("/")
        self._setup_tracing()

    @abstractmethod
    def _setup_tracing(self) -> None:
        """Configure framework-level OTEL/callback instrumentation."""

    def _register(self) -> None:
        """Register this agent with the control plane (fire-and-forget)."""
        registration = AgentRegistration(
            name=self.name,
            description=self.description,
            framework=self.framework,
            version=self.version,
            evaluators=self.evaluators,
            llm_judge_config=self.llm_judge_config,
        )
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{self.control_plane_url}/agents/register",
                    json=registration.model_dump(),
                )
        except Exception:
            pass  # Registration is best-effort; don't block agent execution

    def _report_run(self, report: AgentRunReport) -> None:
        """Send a completed run report to the control plane (fire-and-forget)."""
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{self.control_plane_url}/runs",
                    json=report.model_dump(mode="json"),
                )
        except Exception:
            pass

    async def _report_run_async(self, report: AgentRunReport) -> None:
        """Async version of _report_run."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.control_plane_url}/runs",
                    json=report.model_dump(mode="json"),
                )
        except Exception:
            pass


def agent_run(
    name: str,
    description: str = "",
    evaluators: list[str] | None = None,
    control_plane_url: str = "http://localhost:8500",
    langfuse_trace_id_fn: Callable[..., str] | None = None,
) -> Callable:
    """
    Decorator that wraps any callable to report runs to the control plane.

    The wrapped function is assumed to have already set up its own Langfuse
    tracing (e.g. via @observe). Use langfuse_trace_id_fn to extract the
    trace_id from the result if it's embedded in the return value.

    Usage::

        @agent_run(name="my-agent", evaluators=["llm_judge"])
        def my_agent(prompt: str) -> str:
            return call_my_llm(prompt)
    """
    _evaluators = evaluators or []
    _cp_url = control_plane_url.rstrip("/")

    def decorator(fn: Callable) -> Callable:
        # Register once at decoration time
        registration = AgentRegistration(
            name=name,
            description=description,
            framework=Framework.GENERIC,
            evaluators=_evaluators,
        )
        try:
            with httpx.Client(timeout=3.0) as client:
                client.post(
                    f"{_cp_url}/agents/register",
                    json=registration.model_dump(),
                )
        except Exception:
            pass

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                status = RunStatus.COMPLETED
                output = None
                error = None
                trace_id = str(uuid.uuid4())

                try:
                    output = await fn(*args, **kwargs)
                    if langfuse_trace_id_fn is not None:
                        trace_id = langfuse_trace_id_fn(output)
                    return output
                except Exception as exc:
                    status = RunStatus.FAILED
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    input_val = args[0] if args else kwargs
                    report = AgentRunReport(
                        agent_name=name,
                        trace_id=trace_id,
                        input=input_val,
                        output=output,
                        status=status,
                        latency_ms=latency_ms,
                        error=error,
                    )
                    try:
                        async with httpx.AsyncClient(timeout=3.0) as client:
                            await client.post(
                                f"{_cp_url}/runs",
                                json=report.model_dump(mode="json"),
                            )
                    except Exception:
                        pass

            return async_wrapper

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                status = RunStatus.COMPLETED
                output = None
                error = None
                trace_id = str(uuid.uuid4())

                try:
                    output = fn(*args, **kwargs)
                    if langfuse_trace_id_fn is not None:
                        trace_id = langfuse_trace_id_fn(output)
                    return output
                except Exception as exc:
                    status = RunStatus.FAILED
                    error = str(exc)
                    raise
                finally:
                    latency_ms = (time.perf_counter() - start) * 1000
                    input_val = args[0] if args else kwargs
                    report = AgentRunReport(
                        agent_name=name,
                        trace_id=trace_id,
                        input=input_val,
                        output=output,
                        status=status,
                        latency_ms=latency_ms,
                        error=error,
                    )
                    try:
                        with httpx.Client(timeout=3.0) as client:
                            client.post(
                                f"{_cp_url}/runs",
                                json=report.model_dump(mode="json"),
                            )
                    except Exception:
                        pass

            return sync_wrapper

    return decorator
