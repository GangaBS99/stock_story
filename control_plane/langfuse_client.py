"""Langfuse SDK singleton and convenience helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from control_plane.config import get_settings


@lru_cache
def get_client():
    """Return a cached Langfuse client initialised from settings."""
    from langfuse import Langfuse  # type: ignore

    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def push_score(trace_id: str, name: str, value: float, comment: str | None = None) -> None:
    """Push a numeric score onto a Langfuse trace."""
    client = get_client()
    client.score(
        trace_id=trace_id,
        name=name,
        value=value,
        comment=comment,
    )


def get_traces(limit: int = 50, **filters: Any) -> list[dict]:
    """Fetch recent traces as plain dicts from the Langfuse API."""
    client = get_client()
    try:
        page = client.api.trace.list(limit=limit, **filters)
        items = page.data if hasattr(page, "data") else []
        return [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in items]
    except Exception:
        return []


def get_scores(trace_id: str) -> list[dict]:
    """Fetch all scores attached to a trace."""
    client = get_client()
    try:
        page = client.api.score.list(trace_id=trace_id)
        items = page.data if hasattr(page, "data") else []
        return [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in items]
    except Exception:
        return []


def create_dataset(name: str, description: str = "") -> None:
    client = get_client()
    client.create_dataset(name=name, description=description)


def create_dataset_item(
    dataset_name: str,
    input: Any,
    expected_output: Any | None = None,
    metadata: dict | None = None,
) -> None:
    client = get_client()
    client.create_dataset_item(
        dataset_name=dataset_name,
        input=input,
        expected_output=expected_output,
        metadata=metadata or {},
    )
