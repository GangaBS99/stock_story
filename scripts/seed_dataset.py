"""
Seed a benchmark dataset into Langfuse Datasets.

Run:
    cd agent_platform
    python scripts/seed_dataset.py [--dataset <name>]

Creates a dataset with (input, expected_output) pairs for the market
research agent. Each item's expected_output defines the scoring criteria
used by run_experiment.py:

    must_contain  : list[str]  — keywords the output MUST include
    min_length    : int        — minimum character count expected
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from langfuse import Langfuse

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
)

DEFAULT_DATASET = "market-research/benchmark-v1"

# ─────────────────────────────────────────────────────────────
# Ground-truth items
# Add / edit these to match your actual agent skill commands.
# The "message" is sent verbatim to /process_message.
# ─────────────────────────────────────────────────────────────
ITEMS = [
    {
        "input": {
            "message": "/research NVDA pre-market analysis",
            "description": "NVDA pre-market brief",
        },
        "expected_output": {
            "must_contain": ["NVDA", "pre-market", "volume", "analyst"],
            "min_length": 300,
        },
    },
    {
        "input": {
            "message": "/research What are the key risks for TSLA this quarter?",
            "description": "TSLA risk assessment",
        },
        "expected_output": {
            "must_contain": ["TSLA", "risk", "margin", "delivery"],
            "min_length": 300,
        },
    },
    {
        "input": {
            "message": "/research Give me a fundamental analysis of AAPL",
            "description": "AAPL fundamental analysis",
        },
        "expected_output": {
            "must_contain": ["AAPL", "revenue", "earnings", "P/E"],
            "min_length": 400,
        },
    },
    {
        "input": {
            "message": "/research What is the macro outlook for the semiconductor sector?",
            "description": "Semiconductor sector macro",
        },
        "expected_output": {
            "must_contain": ["semiconductor", "demand", "supply", "AI"],
            "min_length": 400,
        },
    },
    {
        "input": {
            "message": "/research Compare MSFT and GOOGL on cloud growth",
            "description": "MSFT vs GOOGL cloud",
        },
        "expected_output": {
            "must_contain": ["MSFT", "GOOGL", "cloud", "Azure", "GCP"],
            "min_length": 400,
        },
    },
]


def main(dataset_name: str = DEFAULT_DATASET) -> None:
    print(f"Creating dataset '{dataset_name}'…")
    try:
        langfuse.create_dataset(
            name=dataset_name,
            description="Market research benchmark dataset for the planner agent",
            metadata={"version": "1.0", "type": "market-research"},
        )
        print(f"[✓] Dataset created: {dataset_name}")
    except Exception as exc:
        print(f"[~] Dataset may already exist: {exc}")

    for idx, item in enumerate(ITEMS, start=1):
        try:
            langfuse.create_dataset_item(
                dataset_name=dataset_name,
                input=item["input"],
                expected_output=item["expected_output"],
            )
            print(f"[✓] Item {idx}/{len(ITEMS)}: {item['input']['description']}")
        except Exception as exc:
            print(f"[!] Item {idx} failed: {exc}")

    langfuse.flush()
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    print(f"\nDone. View at: {host}  →  Datasets  →  {dataset_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"Dataset name (default: {DEFAULT_DATASET})",
    )
    args = parser.parse_args()
    main(dataset_name=args.dataset)
