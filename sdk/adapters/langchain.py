"""
LangChain → Langfuse adapter.

Uses the official Langfuse LangChain callback handler so all chain/LLM
calls are traced automatically. Wraps chain.invoke() to report runs to
the control plane.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from sdk.connector import BaseConnector
from sdk.schemas import AgentRunReport, Framework, RunStatus


class LangChainAdapter(BaseConnector):
    """
    Adapter for LangChain chains, agents, and LLMs.

    Usage::

        from langchain_openai import ChatOpenAI
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        from sdk.adapters.langchain import LangChainAdapter

        llm = ChatOpenAI(model="gpt-4o")
        chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))

        adapter = LangChainAdapter(
            chain=chain,
            name="my-chain",
            description="Simple LLM chain",
            evaluators=["rule_based"],
        )

        result = adapter.invoke({"input": "Tell me a joke"})
    """

    def __init__(
        self,
        chain: Any,
        name: str,
        description: str = "",
        version: str = "1.0.0",
        evaluators: list[str] | None = None,
        llm_judge_config: Any | None = None,
        control_plane_url: str = "http://localhost:8500",
    ) -> None:
        self._chain = chain
        self._callback_handler = None
        super().__init__(
            name=name,
            description=description,
            framework=Framework.LANGCHAIN,
            version=version,
            evaluators=evaluators,
            llm_judge_config=llm_judge_config,
            control_plane_url=control_plane_url,
        )
        self._register()

    def _setup_tracing(self) -> None:
        """Attach the Langfuse callback handler to the chain."""
        try:
            from langfuse.callback import CallbackHandler

            self._callback_handler = CallbackHandler()
        except ImportError:
            pass

    def invoke(self, input_data: dict[str, Any], **kwargs: Any) -> Any:
        """Invoke the chain synchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        callbacks = kwargs.pop("callbacks", [])
        if self._callback_handler:
            callbacks = [self._callback_handler] + list(callbacks)

        try:
            result = self._chain.invoke(input_data, callbacks=callbacks, **kwargs)
            output = result
            if self._callback_handler and hasattr(
                self._callback_handler, "get_trace_id"
            ):
                tid = self._callback_handler.get_trace_id()
                if tid:
                    trace_id = tid
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
                input=input_data,
                output=str(output) if output is not None else None,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )
            self._report_run(report)

    async def ainvoke(self, input_data: dict[str, Any], **kwargs: Any) -> Any:
        """Invoke the chain asynchronously and report to control plane."""
        start = time.perf_counter()
        status = RunStatus.COMPLETED
        output = None
        error = None
        trace_id = str(uuid.uuid4())

        callbacks = kwargs.pop("callbacks", [])
        if self._callback_handler:
            callbacks = [self._callback_handler] + list(callbacks)

        try:
            result = await self._chain.ainvoke(input_data, callbacks=callbacks, **kwargs)
            output = result
            if self._callback_handler and hasattr(
                self._callback_handler, "get_trace_id"
            ):
                tid = self._callback_handler.get_trace_id()
                if tid:
                    trace_id = tid
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
                input=input_data,
                output=str(output) if output is not None else None,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )
            await self._report_run_async(report)
