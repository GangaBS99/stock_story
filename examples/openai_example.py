"""
Raw OpenAI example — use the OpenAIAdapter for direct API calls.

Run:
    cd agent_platform
    python examples/openai_example.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sdk.adapters.openai import OpenAIAdapter


def main() -> None:
    # --- 1. Create an OpenAIAdapter --------------------------------------------
    #   The adapter wraps the OpenAI client with the Langfuse instrumentation
    #   so every completion call is traced automatically.
    adapter = OpenAIAdapter(
        name="gpt4o-direct",
        description="Direct GPT-4o-mini calls without any framework",
        model="gpt-4o-mini",
        evaluators=["llm_judge", "rule_based"],
        control_plane_url=os.getenv("CONTROL_PLANE_URL", "http://localhost:8500"),
    )

    # --- 2. Use adapter.chat() instead of openai.chat.completions.create() ----
    messages_list = [
        [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ],
        [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Explain what an API is in one sentence."},
        ],
        [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "What is the purpose of a requirements.txt file?"},
        ],
    ]

    for messages in messages_list:
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        print(f"\n[>] {user_msg}")
        response = adapter.chat(messages=messages)
        print(f"[<] {response.choices[0].message.content}")

    print("\n✓ Runs reported to control plane.")


# ── Generic decorator example ─────────────────────────────────────────────────
#
# For any existing function — no framework needed at all:
#
#   from sdk.connector import agent_run
#
#   @agent_run(name="my-custom-tool", evaluators=["rule_based"])
#   def my_tool(query: str) -> str:
#       # your existing logic here
#       return some_llm_call(query)
#
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
