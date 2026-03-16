"""
Raw OpenAI → Langfuse adapter.

Wraps the OpenAI client so every chat.completions.create() call is traced
via the Langfuse @observe decorator and reported to the control plane.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Any

from sdk.connector import BaseConnector
from sdk.schemas import AgentRunReport, Framework, RunStatus


class OpenAIAdapter(BaseConnector):
    """
    Adapter for raw OpenAI API calls.

    Monkey-patches the Langfuse OpenAI wrapper so that all calls made
    through this adapter's .client attribute are automatically traced.

    Usage::

        from sdk.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(
            name="gpt4o-assistant",
            description="Direct GPT-4o calls",
            evaluators=["llm_judge"],
        )

        response = adapter.chat(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(response.choices[0].message.content)
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        model: str = "gpt-4o",
        evaluators: list[str] | None = None,
        llm_judge_config: Any | None = None,
        control_plane_url: str = "http://localhost:8500",
    ) -> None:
        self._model = model
        self.client: Any = None
        super().__init__(
            name=name,
            description=description,
            framework=Framework.OPENAI,
            version=version,
            evaluators=evaluators,
            llm_judge_config=llm_judge_config,
            control_plane_url=control_plane_url,
        )
        self._register()

    def _setup_tracing(self) -> None:
        """
        Use Langfuse's OpenAI wrapper which instruments the client
        transparently via monkey-patching.
        """
        try:
            from langfuse.openai import openai as langfuse_openai

            self.client = langfuse_openai
        except ImportError:
            import openai

            self.client = openai

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        trace_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Send a chat completion request and report to the control plane.

        Args:
            messages: OpenAI messages list.
            model: Override the default model.
            trace_id: Optionally supply a pre-created Langfuse trace_id.
            **kwargs: Forwarded to openai.chat.completions.create().
        """
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        effective_trace_id = trace_id or str(uuid.uuid4())
        used_model = model or self._model

        extra: dict[str, Any] = {}
        if trace_id:
            extra["langfuse_trace_id"] = trace_id

        try:
            response = self.client.chat.completions.create(
                model=used_model,
                messages=messages,
                **extra,
                **kwargs,
            )
            output = response.choices[0].message.content
            return response
        except Exception as exc:
            status = RunStatus.FAILED
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            user_message = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                str(messages),
            )
            report = AgentRunReport(
                agent_name=self.name,
                trace_id=effective_trace_id,
                input=user_message,
                output=output,
                status=status,
                latency_ms=latency_ms,
                error=error,
                metadata={"model": used_model},
            )
            self._report_run(report)

    async def achat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        trace_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of chat()."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        effective_trace_id = trace_id or str(uuid.uuid4())
        used_model = model or self._model

        extra: dict[str, Any] = {}
        if trace_id:
            extra["langfuse_trace_id"] = trace_id

        try:
            import openai as _openai

            async_client = _openai.AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
            response = await async_client.chat.completions.create(
                model=used_model,
                messages=messages,
                **kwargs,
            )
            output = response.choices[0].message.content
            return response
        except Exception as exc:
            status = RunStatus.FAILED
            error = str(exc)
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            user_message = next(
                (m["content"] for m in messages if m.get("role") == "user"),
                str(messages),
            )
            report = AgentRunReport(
                agent_name=self.name,
                trace_id=effective_trace_id,
                input=user_message,
                output=output,
                status=status,
                latency_ms=latency_ms,
                error=error,
                metadata={"model": used_model},
            )
            await self._report_run_async(report)
