"""
PydanticAI → Langfuse adapter.

PydanticAI emits OpenTelemetry spans natively. This adapter:
1. Configures the OTEL exporter to point at Langfuse's OTEL endpoint.
2. Calls Agent.instrument_all() so every PydanticAI agent in the process
   sends spans to Langfuse automatically.
3. Wraps agent.run() / agent.run_sync() to report each run to the
   control plane and trigger the eval pipeline.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from sdk.connector import BaseConnector
from sdk.schemas import AgentRunReport, Framework, RunStatus


class PydanticAIAdapter(BaseConnector):
    """
    Adapter for PydanticAI agents.

    Usage::

        from pydantic_ai import Agent
        from sdk.adapters.pydantic_ai import PydanticAIAdapter

        my_agent = Agent("openai:gpt-4o", system_prompt="You are helpful.")

        adapter = PydanticAIAdapter(
            agent=my_agent,
            name="my-assistant",
            description="General-purpose assistant",
            evaluators=["llm_judge"],
        )

        result = await adapter.run("What is 2+2?")
        print(result.output)
    """

    def __init__(
        self,
        agent: Any,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        evaluators: list[str] | None = None,
        llm_judge_config: Any | None = None,
        control_plane_url: str = "http://localhost:8500",
        # Optional: pass Langfuse credentials explicitly instead of relying on env vars
        langfuse_public_key: str | None = None,
        langfuse_secret_key: str | None = None,
        langfuse_host: str | None = None,
    ) -> None:
        self._agent = agent
        # Store before super().__init__ calls _setup_tracing()
        self._langfuse_public_key = langfuse_public_key
        self._langfuse_secret_key = langfuse_secret_key
        self._langfuse_host = langfuse_host
        super().__init__(
            name=name,
            description=description,
            framework=Framework.PYDANTIC_AI,
            version=version,
            evaluators=evaluators,
            llm_judge_config=llm_judge_config,
            control_plane_url=control_plane_url,
        )
        self._register()

    def _setup_tracing(self) -> None:
        """
        Configure Langfuse tracing for PydanticAI.

        Strategy:
        1. Set LANGFUSE_* env vars from constructor args (highest priority).
        2. Try Langfuse SDK v3 (preferred — it handles its own OTEL exporter).
        3. Fall back to manually wiring OTEL env vars → Langfuse OTLP endpoint.
        4. Always call Agent.instrument_all() so PydanticAI emits spans.
        """
        if self._langfuse_public_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = self._langfuse_public_key
        if self._langfuse_secret_key:
            os.environ["LANGFUSE_SECRET_KEY"] = self._langfuse_secret_key
        if self._langfuse_host:
            os.environ["LANGFUSE_HOST"] = self._langfuse_host

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

        if not public_key or not secret_key:
            print(
                "[PydanticAIAdapter] WARNING: LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY "
                "not set — traces will NOT appear in Langfuse. "
                "Set them in your .env or pass langfuse_public_key/secret_key to the adapter."
            )
            return

        # Try Langfuse SDK v3 (it registers its own OTEL exporter internally)
        langfuse_sdk_ok = False
        try:
            from langfuse import get_client as _lf_get_client
            _lf_get_client()
            langfuse_sdk_ok = True
            print("[PydanticAIAdapter] Langfuse SDK OTEL pipeline initialised.")
        except ImportError:
            pass

        # Fallback: manually point OTEL at Langfuse's HTTP endpoint
        if not langfuse_sdk_ok:
            import base64
            token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
            otlp_endpoint = f"{host.rstrip('/')}/api/public/otel"
            os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)
            os.environ.setdefault(
                "OTEL_EXPORTER_OTLP_HEADERS", f"Authorization=Basic {token}"
            )
            print(f"[PydanticAIAdapter] Manual OTEL endpoint set: {otlp_endpoint}")

        # Always instrument — this must happen regardless of which path above ran
        try:
            from pydantic_ai.agent import Agent
            Agent.instrument_all()
            print("[PydanticAIAdapter] Agent.instrument_all() called successfully.")
        except ImportError as exc:
            print(f"[PydanticAIAdapter] WARNING: pydantic-ai not importable: {exc}")

    async def run(self, prompt: str, **kwargs: Any) -> Any:
        """Run the agent asynchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        try:
            result = await self._agent.run(prompt, **kwargs)
            output = result.output if hasattr(result, "output") else str(result)
            # PydanticAI >= 0.0.20 exposes _trace_id on the result
            if hasattr(result, "_trace_id") and result._trace_id:
                trace_id = str(result._trace_id)
            return result
        except Exception as exc:
            status = RunStatus.FAILED
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            report = AgentRunReport(
                agent_name=self.name,
                trace_id=trace_id,
                input=prompt,
                output=output,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )
            await self._report_run_async(report)

    def run_sync(self, prompt: str, **kwargs: Any) -> Any:
        """Run the agent synchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        try:
            result = self._agent.run_sync(prompt, **kwargs)
            output = result.output if hasattr(result, "output") else str(result)
            if hasattr(result, "_trace_id") and result._trace_id:
                trace_id = str(result._trace_id)
            return result
        except Exception as exc:
            status = RunStatus.FAILED
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            report = AgentRunReport(
                agent_name=self.name,
                trace_id=trace_id,
                input=prompt,
                output=output,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )
            self._report_run(report)
