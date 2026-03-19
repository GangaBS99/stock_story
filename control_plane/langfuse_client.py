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
    # Best-effort push to Langfuse; ignore SDK/version mismatches so the control plane never 500s.
    try:
        # Different Langfuse Python SDK versions expose scores slightly differently.
        # Prefer the typed API client if available.
        if hasattr(getattr(client, "api", None), "scores"):
            scores_client = client.api.scores
            if hasattr(scores_client, "create"):
                scores_client.create(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                    comment=comment,
                )
        elif hasattr(client, "score"):
            # Older SDKs exposed a top-level score() helper.
            client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
            )
    except Exception:
        # Don't let Langfuse SDK issues break the control plane; internal scores are still stored.
        pass


_LANGFUSE_MAX_PAGE_SIZE = 100


def get_traces(limit: int = 50, **filters: Any) -> list[dict]:
    """Fetch recent traces as plain dicts from the Langfuse API.

    Paginates automatically when limit > 100 (the Langfuse API hard cap).
    """
    client = get_client()
    results: list[dict] = []
    remaining = limit
    page_num = 1

    while remaining > 0:
        page_size = min(remaining, _LANGFUSE_MAX_PAGE_SIZE)
        try:
            page = client.api.trace.list(limit=page_size, page=page_num, **filters)
            items = page.data if hasattr(page, "data") else []
            if not items:
                break
            results.extend(
                t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in items
            )
            remaining -= len(items)
            # Stop if the API returned fewer items than requested (last page)
            if len(items) < page_size:
                break
            page_num += 1
        except Exception:
            break

    return results


def get_trace(trace_id: str) -> dict | None:
    """Fetch a single trace by id."""
    client = get_client()
    try:
        trace = client.api.trace.get(trace_id=trace_id)
        if trace is None:
            return None
        return trace.model_dump() if hasattr(trace, "model_dump") else dict(trace)
    except Exception:
        return None


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
