"""
Seed versioned prompts into Langfuse Prompt Management.

Run:
    cd agent_platform
    python scripts/seed_prompts.py

Prompts are versioned in Langfuse. After running this script you can:
  • View/edit them in Langfuse UI → Prompts
  • Fetch them at runtime via langfuse.get_prompt("<name>")
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from langfuse import Langfuse  # type: ignore

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
)

PROMPTS = [
    {
        "name": "platform/llm-judge",
        "prompt": (
            "You are an impartial evaluator for AI agent outputs.\n\n"
            "INPUT:\n{{input}}\n\n"
            "OUTPUT:\n{{output}}\n\n"
            "Rate the output on the following dimensions. "
            "Return ONLY valid JSON with exactly these two keys:\n"
            '{"quality": <float 0.0-1.0>, "relevance": <float 0.0-1.0>, '
            '"quality_comment": "<one sentence>", "relevance_comment": "<one sentence>"}'
        ),
        "labels": ["production"],
        "config": {"model": "gpt-4o-mini", "temperature": 0},
    },
    {
        "name": "platform/system-assistant",
        "prompt": (
            "You are a helpful, concise, and accurate AI assistant. "
            "Answer in 2-3 sentences unless asked otherwise."
        ),
        "labels": ["production"],
        "config": {},
    },
]


def main() -> None:
    for p in PROMPTS:
        try:
            langfuse.create_prompt(
                name=p["name"],
                prompt=p["prompt"],
                labels=p.get("labels", []),
                config=p.get("config", {}),
            )
            print(f"[✓] Created prompt: {p['name']}")
        except Exception as exc:
            print(f"[!] Failed to create prompt '{p['name']}': {exc}")

    langfuse.flush()
    print("\nDone. View prompts at: "
          f"{os.getenv('LANGFUSE_HOST', 'http://localhost:3000')}/prompts")


if __name__ == "__main__":
    main()
