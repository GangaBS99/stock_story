"""In-memory prompt library with versioning and activation by environment."""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any


class PromptRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        # name -> {"versions": [...], "active_by_env": {"dev": 2, "prod": 1}}
        self._store: dict[str, dict[str, Any]] = {}

    def create_version(
        self,
        *,
        name: str,
        prompt: str,
        environment: str = "default",
        labels: list[str] | None = None,
        config: dict[str, Any] | None = None,
        created_by: str = "system",
        activate: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            rec = self._store.setdefault(name, {"versions": [], "active_by_env": {}})
            versions: list[dict[str, Any]] = rec["versions"]
            # Idempotent behavior: if latest version in same env has identical content,
            # avoid creating a duplicate version on repeated imports/restarts.
            if versions:
                latest = versions[-1]
                if (
                    latest.get("environment") == environment
                    and latest.get("prompt") == prompt
                    and latest.get("labels", []) == (labels or [])
                    and latest.get("config", {}) == (config or {})
                ):
                    if activate:
                        rec["active_by_env"][environment] = latest["version"]
                    return {
                        **latest,
                        "is_active": rec["active_by_env"].get(environment) == latest["version"],
                    }
            next_version = len(versions) + 1
            now = datetime.utcnow().isoformat()
            item = {
                "name": name,
                "version": next_version,
                "environment": environment,
                "prompt": prompt,
                "labels": labels or [],
                "config": config or {},
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            }
            versions.append(item)
            if activate:
                rec["active_by_env"][environment] = next_version
            return {**item, "is_active": rec["active_by_env"].get(environment) == next_version}

    def list_prompts(self) -> list[dict[str, Any]]:
        with self._lock:
            result: list[dict[str, Any]] = []
            for name, rec in self._store.items():
                versions: list[dict[str, Any]] = rec["versions"]
                latest = versions[-1] if versions else None
                result.append(
                    {
                        "name": name,
                        "latest_version": latest["version"] if latest else 0,
                        "latest_environment": latest["environment"] if latest else "default",
                        "latest_preview": (latest["prompt"][:120] + "...") if latest and len(latest["prompt"]) > 120 else (latest["prompt"] if latest else ""),
                        "labels": latest["labels"] if latest else [],
                        "active_by_env": dict(rec["active_by_env"]),
                        "version_count": len(versions),
                        "updated_at": latest["updated_at"] if latest else "",
                    }
                )
            return sorted(result, key=lambda x: x["name"])

    def list_versions(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
            rec = self._store.get(name)
            if not rec:
                return []
            active_by_env: dict[str, int] = rec["active_by_env"]
            rows: list[dict[str, Any]] = []
            for item in rec["versions"]:
                env = item["environment"]
                rows.append(
                    {
                        **item,
                        "is_active": active_by_env.get(env) == item["version"],
                    }
                )
            return rows

    def activate(self, *, name: str, version: int, environment: str) -> dict[str, Any] | None:
        with self._lock:
            rec = self._store.get(name)
            if not rec:
                return None
            found = next((v for v in rec["versions"] if v["version"] == version), None)
            if not found:
                return None
            rec["active_by_env"][environment] = version
            return {
                "name": name,
                "version": version,
                "environment": environment,
                "status": "active",
            }

    def get_active(self, *, name: str, environment: str = "default") -> dict[str, Any] | None:
        with self._lock:
            rec = self._store.get(name)
            if not rec:
                return None
            version = rec["active_by_env"].get(environment)
            if version is None:
                return None
            found = next((v for v in rec["versions"] if v["version"] == version), None)
            if not found:
                return None
            return {
                **found,
                "is_active": True,
            }


prompt_registry = PromptRegistry()
