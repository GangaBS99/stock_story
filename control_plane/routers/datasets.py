from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from control_plane.langfuse_client import create_dataset, create_dataset_item, get_client

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetCreateRequest(BaseModel):
    name: str
    description: str = ""


class DatasetItemRequest(BaseModel):
    input: Any
    expected_output: Any = None
    metadata: dict[str, Any] = {}


@router.post("", summary="Create a new dataset in Langfuse")
def create_dataset_endpoint(req: DatasetCreateRequest) -> dict:
    try:
        create_dataset(name=req.name, description=req.description)
        return {"status": "created", "name": req.name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{name}/items", summary="Add an item to a dataset")
def add_dataset_item(name: str, item: DatasetItemRequest) -> dict:
    try:
        create_dataset_item(
            dataset_name=name,
            input=item.input,
            expected_output=item.expected_output,
            metadata=item.metadata,
        )
        return {"status": "added", "dataset": name}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", summary="List all datasets from Langfuse")
def list_datasets(limit: int = 20) -> list[dict]:
    try:
        client = get_client()
        page = client.api.datasets.list(limit=limit)
        items = page.data if hasattr(page, "data") else []
        return [
            d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in items
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{name}/items", summary="List items in a dataset")
def list_dataset_items(name: str, limit: int = 50) -> list[dict]:
    try:
        client = get_client()
        dataset = client.get_dataset(name=name)
        items = dataset.items if hasattr(dataset, "items") else []
        return [
            i.model_dump() if hasattr(i, "model_dump") else dict(i)
            for i in items[:limit]
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
