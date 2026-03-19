"""Auto-import prompt definitions from project Python source files."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from control_plane.prompt_registry import prompt_registry

TARGET_ASSIGN_NAMES = {
    "system_prompt",
    "prompt_template",
    "template",
    "SYSTEM_PROMPT",
    "PROMPT",
}

TARGET_CALL_NAMES = {
    "Agent",
    "PromptTemplate",
    "ChatPromptTemplate",
    "SystemMessagePromptTemplate",
    "HumanMessagePromptTemplate",
}


def _get_call_name(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""


def _extract_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        # Keep f-strings only when they have static pieces.
        text = "".join(
            part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str)
        ).strip()
        return text or None
    return None


def extract_prompts_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        tree = ast.parse(source)
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(name in TARGET_ASSIGN_NAMES for name in target_names):
                text = _extract_str(node.value)
                if text and text.strip():
                    rows.append(
                        {
                            "kind": "assign",
                            "name_hint": target_names[0] if target_names else "prompt",
                            "prompt": text.strip(),
                            "line": getattr(node, "lineno", 0),
                        }
                    )
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in TARGET_ASSIGN_NAMES:
                text = _extract_str(node.value) if node.value is not None else None
                if text and text.strip():
                    rows.append(
                        {
                            "kind": "annassign",
                            "name_hint": node.target.id,
                            "prompt": text.strip(),
                            "line": getattr(node, "lineno", 0),
                        }
                    )
        elif isinstance(node, ast.Call):
            call_name = _get_call_name(node)
            if call_name in TARGET_CALL_NAMES:
                for kw in node.keywords:
                    if kw.arg in {"system_prompt", "template"}:
                        text = _extract_str(kw.value)
                        if text and text.strip():
                            rows.append(
                                {
                                    "kind": f"call:{call_name}",
                                    "name_hint": kw.arg,
                                    "prompt": text.strip(),
                                    "line": getattr(node, "lineno", 0),
                                }
                            )

    # Deduplicate prompts within the same file by content
    seen: set[str] = set()
    unique_rows: list[dict[str, Any]] = []
    for row in rows:
        key = row["prompt"]
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def import_prompts_from_roots(roots: list[Path], environment: str = "default") -> dict[str, int]:
    imported = 0
    scanned_files = 0
    seen_global: set[str] = set()

    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            # Skip virtual env and cache folders.
            path_str = str(path).lower()
            if any(skip in path_str for skip in ("\\venv\\", "\\.venv\\", "__pycache__")):
                continue
            scanned_files += 1
            rel = path.relative_to(root)
            rows = extract_prompts_from_file(path)
            for i, row in enumerate(rows, start=1):
                text = row["prompt"]
                global_key = f"{text}"
                if global_key in seen_global:
                    continue
                seen_global.add(global_key)
                name = f"{rel.as_posix()}::{row['name_hint']}::{row['line']}::{i}"
                prompt_registry.create_version(
                    name=name,
                    prompt=text,
                    environment=environment,
                    labels=["auto-import", "source-code", row["kind"]],
                    config={"source_file": rel.as_posix(), "line": row["line"], "kind": row["kind"]},
                    created_by="prompt-importer",
                    activate=True,
                )
                imported += 1

    return {"imported": imported, "scanned_files": scanned_files}
