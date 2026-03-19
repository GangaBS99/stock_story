"""
Agent Observability Platform — FastAPI Control Plane
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from control_plane.config import get_settings
from control_plane.prompt_importer import import_prompts_from_roots
from control_plane.routers import agents, dashboard, datasets, evals, prompts, runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(
        f"[control-plane] Langfuse host: {settings.langfuse_host}\n"
        f"[control-plane] Control plane URL: {settings.control_plane_url}"
    )
    try:
        repo_root = Path(__file__).resolve().parents[2]
        roots = [
            repo_root / "agentic-backend" / "Agentic-backend" / "src",
            repo_root / "stockStoryServer" / "backend",
            repo_root / "stock_story",
        ]
        stats = import_prompts_from_roots(roots=roots, environment="default")
        print(
            f"[control-plane] Prompt auto-import: imported={stats['imported']} "
            f"scanned_files={stats['scanned_files']}"
        )
    except Exception:
        pass
    yield
    # Flush Langfuse on shutdown
    try:
        from control_plane.langfuse_client import get_client

        get_client().flush()
    except Exception:
        pass


app = FastAPI(
    title="Agent Observability Platform",
    description=(
        "Framework-agnostic control plane for LLM agent tracing, "
        "evaluation, and dataset management on top of Langfuse."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(runs.router)
app.include_router(evals.router)
app.include_router(datasets.router)
app.include_router(dashboard.router)
app.include_router(prompts.router)


@app.get("/", tags=["health"])
def root():
    return {
        "service": "Agent Observability Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["health"])
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "langfuse_host": settings.langfuse_host,
    }
