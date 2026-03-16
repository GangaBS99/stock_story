from __future__ import annotations

from fastapi import APIRouter, HTTPException

from control_plane.registry import registry
from sdk.schemas import AgentRegistration

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/register", summary="Register an agent with the platform")
def register_agent(registration: AgentRegistration) -> dict:
    entry = registry.register(registration)
    return {"status": "registered", "agent": entry}


@router.get("", summary="List all registered agents")
def list_agents() -> list[dict]:
    return registry.list_all()


@router.get("/{name}", summary="Get a specific agent by name")
def get_agent(name: str) -> dict:
    agent = registry.get(name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return agent


@router.delete("/{name}", summary="Remove an agent from the registry")
def delete_agent(name: str) -> dict:
    removed = registry.delete(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {"status": "removed", "name": name}
