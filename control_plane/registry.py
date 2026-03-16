"""In-memory agent registry — register once, query any time."""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from sdk.schemas import AgentRegistration


class AgentRegistry:
    """Thread-safe singleton registry for agent metadata."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def register(self, registration: AgentRegistration) -> dict[str, Any]:
        entry = {
            **registration.model_dump(),
            "registered_at": datetime.utcnow().isoformat(),
        }
        with self._lock:
            self._agents[registration.name] = entry
        return entry

    def get(self, name: str) -> dict[str, Any] | None:
        return self._agents.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._agents.values())

    def delete(self, name: str) -> bool:
        with self._lock:
            if name in self._agents:
                del self._agents[name]
                return True
        return False

    def __len__(self) -> int:
        return len(self._agents)


# Module-level singleton
registry = AgentRegistry()
