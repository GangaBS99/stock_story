"""
PydanticAI example — connect any PydanticAI agent to the platform.

Run:
    cd agent_platform
    python examples/pydantic_ai_example.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from pydantic_ai import Agent

from sdk.adapters.pydantic_ai import PydanticAIAdapter


async def main() -> None:
    # --- 1. Define any PydanticAI agent ----------------------------------------
    research_agent = Agent(
        "openai:gpt-4o-mini",
        system_prompt=(
            "You are a concise research assistant. "
            "Answer questions clearly in 2-3 sentences."
        ),
        instrument=True,
    )

    # --- 2. Wrap with PydanticAIAdapter ----------------------------------------
    #   This single call:
    #   • Configures OTEL → Langfuse so every run is traced automatically
    #   • Registers the agent with the control plane
    #   • Will report each run + trigger evaluators after execution
    adapter = PydanticAIAdapter(
        agent=research_agent,
        name="research-assistant",
        description="Answers research questions concisely using GPT-4o-mini",
        evaluators=["llm_judge", "rule_based"],
        control_plane_url=os.getenv("CONTROL_PLANE_URL", "http://localhost:8500"),
    )

    # --- 3. Run as normal --------------------------------------------------------
    prompts = [
        "What is the difference between RAG and fine-tuning?",
        "Explain OpenTelemetry in one paragraph.",
        "What are the main benefits of using Langfuse for LLM observability?",
    ]

    for prompt in prompts:
        print(f"\n[>] {prompt}")
        result = await adapter.run(prompt)
        print(f"[<] {result.output}")

    print("\n✓ Runs reported to control plane. Check the dashboard at http://localhost:8501")
    print(f"✓ Traces visible in Langfuse at {os.getenv('LANGFUSE_HOST', 'http://localhost:3000')}/traces")


if __name__ == "__main__":
    asyncio.run(main())
