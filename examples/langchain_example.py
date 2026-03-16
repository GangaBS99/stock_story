"""
LangChain example — connect any LangChain chain to the platform.

Run:
    cd agent_platform
    python examples/langchain_example.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from sdk.adapters.langchain import LangChainAdapter


def main() -> None:
    # --- 1. Define any LangChain chain -----------------------------------------
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant. Be concise."),
            ("human", "{input}"),
        ]
    )
    chain = prompt | llm

    # --- 2. Wrap with LangChainAdapter ------------------------------------------
    #   The adapter attaches a Langfuse callback handler so all LLM calls
    #   are traced. Each invoke() is reported to the control plane.
    adapter = LangChainAdapter(
        chain=chain,
        name="gpt4o-mini-chain",
        description="Simple GPT-4o-mini LangChain chain",
        evaluators=["llm_judge", "rule_based"],
        control_plane_url=os.getenv("CONTROL_PLANE_URL", "http://localhost:8500"),
    )

    # --- 3. Invoke as normal -----------------------------------------------------
    inputs = [
        {"input": "What is vector similarity search?"},
        {"input": "Explain the difference between sync and async Python."},
        {"input": "What is Pydantic used for?"},
    ]

    for inp in inputs:
        print(f"\n[>] {inp['input']}")
        result = adapter.invoke(inp)
        content = result.content if hasattr(result, "content") else str(result)
        print(f"[<] {content}")

    print("\n✓ Runs reported to control plane.")


if __name__ == "__main__":
    main()
