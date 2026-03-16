"""
Run a dataset experiment against the Stock Story /process_message endpoint.

Uses Langfuse SDK v4's native run_experiment() API which handles tracing,
dataset linking, and scoring automatically.

Usage:
    cd agent_platform
    python3 scripts/run_experiment.py \\
        --dataset  morning-note-benchmark \\
        --experiment-name "gemini-2.5-pro-v1" \\
        --agent-url  http://127.0.0.1:7000
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import re

import httpx
from langfuse import Langfuse
from langfuse.experiment import Evaluation
from google import genai as google_genai

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
)

DEFAULT_DATASET = "morning-note-benchmark"
DEFAULT_EXPERIMENT = "baseline-run"
DEFAULT_AGENT_URL = "http://127.0.0.1:7000"


# ─────────────────────────────────────────────────────────────
# Task — calls the agent HTTP endpoint
# ─────────────────────────────────────────────────────────────

def make_task(agent_url: str):
    """Returns a task function closed over agent_url."""

    async def task(*, item, **kwargs):
        raw_input = item.input
        if isinstance(raw_input, dict):
            message = (
                raw_input.get("question")
                or raw_input.get("message")
                or raw_input.get("prompt")
                or raw_input.get("query")
                or str(raw_input)
            )
        else:
            message = str(raw_input)

        session_id = f"experiment-{uuid.uuid4().hex[:8]}"

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{agent_url.rstrip('/')}/process_message",
                json={"message": message, "session_id": session_id},
            )
            resp.raise_for_status()
            data = resp.json()

        output = data.get("output", "")
        print(f"  ✓ {message[:60]}…  →  {output[:80]}…")
        return output

    return task


# ─────────────────────────────────────────────────────────────
# Evaluators — each receives (input, output, expected_output)
# and returns {"name": ..., "value": 0-1} or a list of those
# ─────────────────────────────────────────────────────────────

def eval_output_present(*, output, **kwargs):
    return Evaluation(
        name="output_present",
        value=1.0 if str(output).strip() else 0.0,
    )


def eval_keyword_coverage(*, output, expected_output, **kwargs):
    if not expected_output:
        return []
    keywords = expected_output.get("must_contain", [])
    if not keywords:
        return []
    output_lower = str(output).lower()
    hits = sum(1 for kw in keywords if kw.lower() in output_lower)
    score = round(hits / len(keywords), 3)
    return Evaluation(
        name="keyword_coverage",
        value=score,
        comment=f"{hits}/{len(keywords)} keywords found",
    )


def eval_min_length(*, output, expected_output, **kwargs):
    if not expected_output:
        return []
    min_len = expected_output.get("min_length")
    if min_len is None:
        return []
    length = len(str(output))
    value = 1.0 if length >= min_len else round(length / min_len, 3)
    return Evaluation(
        name="length_ok",
        value=value,
        comment=f"{length} chars (min: {min_len})",
    )


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, stripping punctuation."""
    return set(re.findall(r"\b[a-z0-9]+\b", text.lower()))


def eval_answer_overlap(*, output, expected_output, **kwargs):
    """
    Token-level overlap (Jaccard similarity) between agent output
    and the reference answer in expected_output.
    Fast, free — no LLM required.
    """
    if not expected_output:
        return []
    reference = expected_output.get("answer", "")
    if not reference:
        return []

    out_tokens = _tokenize(str(output))
    ref_tokens = _tokenize(str(reference))

    if not ref_tokens:
        return []

    intersection = out_tokens & ref_tokens
    union = out_tokens | ref_tokens
    jaccard = round(len(intersection) / len(union), 3) if union else 0.0

    # recall: what fraction of reference tokens appear in the output
    recall = round(len(intersection) / len(ref_tokens), 3)

    return [
        Evaluation(
            name="answer_token_overlap",
            value=jaccard,
            comment=f"Jaccard={jaccard}  Recall={recall}  ({len(intersection)} shared tokens)",
        ),
        Evaluation(
            name="answer_recall",
            value=recall,
            comment=f"{len(intersection)}/{len(ref_tokens)} reference tokens covered",
        ),
    ]


async def eval_answer_llm_judge(*, input, output, expected_output, **kwargs):
    """
    LLM judge (Gemini 2.0 Flash): rates how well the agent output matches
    the reference answer on a 0–10 scale, then normalises to 0–1.
    Only runs when expected_output contains an 'answer' field.
    """
    if not expected_output:
        return []
    reference = expected_output.get("answer", "")
    if not reference:
        return []

    google_key = os.getenv("GOOGLE_API_KEY", "")
    if not google_key:
        return Evaluation(
            name="answer_llm_match",
            value=0.0,
            comment="GOOGLE_API_KEY not set — skipped",
        )

    prompt = f"""\
You are an expert financial analyst evaluating an AI-generated market research response.

USER QUERY:
{input}

REFERENCE ANSWER (ground truth):
{reference[:2000]}

AGENT OUTPUT:
{str(output)[:2000]}

Score how well the agent output matches the reference answer on these criteria:
- Factual alignment: are key claims consistent?
- Coverage: does it address the same topics?
- Quality: is it as insightful and specific?

Reply with ONLY a JSON object: {{"score": <0-10>, "reason": "<one sentence>"}}"""

    try:
        import json
        client = google_genai.Client(api_key=google_key)
        resp = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = resp.text.strip()
        # strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        score_10 = float(data.get("score", 0))
        score_01 = round(score_10 / 10, 2)
        reason = data.get("reason", "")
        return Evaluation(
            name="answer_llm_match",
            value=score_01,
            comment=f"{score_10}/10 — {reason}",
        )
    except Exception as exc:
        return Evaluation(
            name="answer_llm_match",
            value=0.0,
            comment=f"Judge failed: {exc}",
        )


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run_experiment_cmd(
    dataset_name: str,
    experiment_name: str,
    agent_url: str,
) -> None:
    # fetch dataset items
    try:
        dataset = langfuse.get_dataset(name=dataset_name)
    except Exception as exc:
        print(f"[!] Could not fetch dataset '{dataset_name}': {exc}")
        print("    Create it in the Langfuse UI or run:")
        print("    python3 scripts/seed_dataset.py --dataset <name>")
        return

    items = dataset.items or []
    print(f"Dataset   : {dataset_name}")
    print(f"Experiment: {experiment_name}")
    print(f"Agent URL : {agent_url}")
    print(f"Items     : {len(items)}\n")

    result = langfuse.run_experiment(
        name=dataset_name,
        run_name=experiment_name,
        data=items,
        task=make_task(agent_url),
        evaluators=[
            eval_output_present,
            eval_keyword_coverage,
            eval_min_length,
            eval_answer_overlap,       # token overlap vs reference answer (free)
            eval_answer_llm_judge,     # LLM judge vs reference answer (GPT-4o-mini)
        ],
        metadata={"agent_url": agent_url},
    )

    print(f"\n{'─'*50}")
    print(f"Experiment run: {result.run_name}")
    if result.dataset_run_url:
        print(f"View results : {result.dataset_run_url}")
    else:
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        print(f"View results : {host}  →  Datasets  →  {dataset_name}")


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a Langfuse dataset experiment against the agent HTTP endpoint"
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Langfuse dataset name (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--experiment-name",
        default=DEFAULT_EXPERIMENT,
        help=f"Experiment run label shown in Langfuse (default: {DEFAULT_EXPERIMENT})",
    )
    parser.add_argument(
        "--agent-url",
        default=os.getenv("AGENT_URL", DEFAULT_AGENT_URL),
        help=f"Base URL of the /process_message endpoint (default: {DEFAULT_AGENT_URL})",
    )
    args = parser.parse_args()

    run_experiment_cmd(
        dataset_name=args.dataset,
        experiment_name=args.experiment_name,
        agent_url=args.agent_url,
    )
