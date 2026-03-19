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

    @staticmethod
    def _extract_result_messages(result: Any) -> list[Any]:
        """Best-effort extraction of run messages across pydantic-ai versions."""
        candidates: list[list[Any]] = []
        for accessor in ("all_messages", "new_messages"):
            attr = getattr(result, accessor, None)
            if callable(attr):
                try:
                    msgs = attr()
                    if isinstance(msgs, (list, tuple)):
                        candidates.append(list(msgs))
                except Exception:
                    pass
        for attr_name in ("_all_messages", "messages", "message_history", "_messages"):
            msgs = getattr(result, attr_name, None)
            if isinstance(msgs, (list, tuple)):
                candidates.append(list(msgs))
        return max(candidates, key=len) if candidates else []

    @classmethod
    def _estimate_internal_steps_from_result(cls, result: Any) -> int:
        """
        Estimate internal turns from model/tool message stream.
        Prefer model responses as the closest proxy for decision turns.
        """
        messages = cls._extract_result_messages(result)
        if not messages:
            return 0

        model_responses = 0
        assistant_like = 0
        for msg in messages:
            role = str(getattr(msg, "role", "") or "").lower()
            name = msg.__class__.__name__.lower()
            if "modelresponse" in name:
                model_responses += 1
            if role in ("assistant", "model", "tool"):
                assistant_like += 1
            elif any(k in name for k in ("modelrequest", "modelresponse", "toolcall", "toolreturn")):
                assistant_like += 1

        return model_responses if model_responses > 0 else assistant_like

    async def run(self, prompt: str, **kwargs: Any) -> Any:
        """Run the agent asynchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        # Optional observability metadata (e.g. decision turns) passed by caller.
        # We also derive some metadata here (like turns from message_history).
        metadata = kwargs.pop("metadata", {}) or {}

        # If the caller provided message_history, approximate base turns
        # as the number of user/assistant messages in the history plus this prompt.
        message_history = kwargs.get("message_history")
        try:
            if isinstance(message_history, (list, tuple)):
                turns = sum(
                    1
                    for msg in message_history
                    if getattr(msg, "role", "") in ("user", "assistant")
                ) + 1
                # Only set if not already provided by the caller.
                metadata.setdefault("turns", turns)
                metadata.setdefault("base_turns", turns)
        except Exception:
            # Never let observability bookkeeping break the agent run.
            pass

        try:
            result = await self._agent.run(prompt, **kwargs)
            output = result.output if hasattr(result, "output") else str(result)
            # Include internal agent reasoning/tool activity in turn count when available.
            try:
                deps = kwargs.get("deps")
                deps_steps = int(getattr(deps, "reasoning_steps", 0) or 0) if deps is not None else 0
                tool_steps = 0
                if deps is not None:
                    tool_calls = getattr(deps, "tool_calls", None)
                    if isinstance(tool_calls, list):
                        tool_steps = len(tool_calls)
                result_steps = self._estimate_internal_steps_from_result(result)
                internal_steps = max(deps_steps, tool_steps, result_steps)

                base_turns = int(metadata.get("turns", 1) or 1)
                metadata["internal_reasoning_steps"] = internal_steps
                metadata["turns"] = base_turns + internal_steps
                metadata.setdefault("decision_turns", metadata["turns"])
            except Exception:
                pass
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
                metadata=metadata,
            )
            await self._report_run_async(report)

    def run_sync(self, prompt: str, **kwargs: Any) -> Any:
        """Run the agent synchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        # Optional observability metadata for sync runs as well.
        metadata = kwargs.pop("metadata", {}) or {}

        message_history = kwargs.get("message_history")
        try:
            if isinstance(message_history, (list, tuple)):
                turns = sum(
                    1
                    for msg in message_history
                    if getattr(msg, "role", "") in ("user", "assistant")
                ) + 1
                metadata.setdefault("turns", turns)
                metadata.setdefault("base_turns", turns)
        except Exception:
            pass

        try:
            result = self._agent.run_sync(prompt, **kwargs)
            output = result.output if hasattr(result, "output") else str(result)
            try:
                deps = kwargs.get("deps")
                deps_steps = int(getattr(deps, "reasoning_steps", 0) or 0) if deps is not None else 0
                tool_steps = 0
                if deps is not None:
                    tool_calls = getattr(deps, "tool_calls", None)
                    if isinstance(tool_calls, list):
                        tool_steps = len(tool_calls)
                result_steps = self._estimate_internal_steps_from_result(result)
                internal_steps = max(deps_steps, tool_steps, result_steps)

                base_turns = int(metadata.get("turns", 1) or 1)
                metadata["internal_reasoning_steps"] = internal_steps
                metadata["turns"] = base_turns + internal_steps
                metadata.setdefault("decision_turns", metadata["turns"])
            except Exception:
                pass
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
                metadata=metadata,
            )
            self._report_run(report)
