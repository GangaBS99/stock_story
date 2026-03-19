from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from control_plane.prompt_importer import import_prompts_from_roots
from control_plane.prompt_registry import prompt_registry
from pathlib import Path

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    environment: str = Field("default")
    labels: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field("system")
    activate: bool = Field(True)


class PromptActivateRequest(BaseModel):
    version: int = Field(..., ge=1)
    environment: str = Field("default")


@router.get("", summary="List prompt definitions")
def list_prompts() -> list[dict]:
    return prompt_registry.list_prompts()


@router.post("", summary="Create a new prompt version")
def create_prompt_version(payload: PromptCreateRequest) -> dict:
    return prompt_registry.create_version(
        name=payload.name,
        prompt=payload.prompt,
        environment=payload.environment,
        labels=payload.labels,
        config=payload.config,
        created_by=payload.created_by,
        activate=payload.activate,
    )


@router.get("/{name:path}/versions", summary="List all versions for a prompt")
def list_prompt_versions(name: str) -> list[dict]:
    rows = prompt_registry.list_versions(name)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return rows


@router.get("/{name:path}/active", summary="Get active prompt version by environment")
def get_active_prompt(name: str, environment: str = Query("default")) -> dict:
    row = prompt_registry.get_active(name=name, environment=environment)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active prompt found for '{name}' in environment '{environment}'",
        )
    return row


@router.post("/{name:path}/activate", summary="Activate a prompt version for an environment")
def activate_prompt(name: str, payload: PromptActivateRequest) -> dict:
    row = prompt_registry.activate(
        name=name,
        version=payload.version,
        environment=payload.environment,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prompt '{name}' version '{payload.version}' not found",
        )
    return row


@router.post("/import-source", summary="Import prompt definitions from project source files")
def import_source_prompts() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    roots = [
        repo_root / "agentic-backend" / "Agentic-backend" / "src",
        repo_root / "stockStoryServer" / "backend",
        repo_root / "stock_story",
    ]
    stats = import_prompts_from_roots(roots=roots, environment="default")
    return {"status": "imported", **stats}
