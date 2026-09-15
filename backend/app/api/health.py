"""
api/health.py — Health check endpoint.
Reports per-component status: db, retrieval index, llm_primary, llm_fallback.
Returns HTTP 200 always (even when degraded) — 5xx only for true crashes.
The UI reads the component statuses to show live banners.
"""
from __future__ import annotations

import os

from fastapi import APIRouter

from app.config import settings
from app.schemas import ComponentStatus, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    components: dict[str, ComponentStatus] = {}

    # ── DB ──────────────────────────────────────────────────────────────────
    try:
        from app.db import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        components["db"] = ComponentStatus(status="ok")
    except Exception as exc:
        components["db"] = ComponentStatus(status="error", detail=str(exc))

    # ── Retrieval index ──────────────────────────────────────────────────────
    index_path = settings.bm25_index_path
    if os.path.exists(index_path):
        components["retrieval"] = ComponentStatus(status="ok", detail=index_path)
    else:
        components["retrieval"] = ComponentStatus(
            status="degraded",
            detail="BM25 index not built yet — POST /api/admin/reindex to build",
        )

    # ── LLM primary ─────────────────────────────────────────────────────────
    components["llm_primary"] = _check_provider(settings.llm_provider)

    # ── LLM fallback ────────────────────────────────────────────────────────
    if settings.llm_fallback_provider:
        components["llm_fallback"] = _check_provider(settings.llm_fallback_provider)
    else:
        components["llm_fallback"] = ComponentStatus(
            status="unconfigured", detail="LLM_FALLBACK_PROVIDER not set"
        )

    # Overall roll-up
    statuses = {c.status for c in components.values()}
    if "error" in statuses:
        overall = "error"
    elif "degraded" in statuses or "unconfigured" in statuses:
        overall = "degraded"
    else:
        overall = "ok"

    return HealthResponse(
        status=overall,
        version=settings.app_version,
        components=components,
    )


def _check_provider(provider: str) -> ComponentStatus:
    if provider == "mock":
        return ComponentStatus(status="ok", detail="mock provider always available")
    if provider == "anthropic":
        if settings.anthropic_api_key:
            return ComponentStatus(
                status="ok", detail=f"model={settings.anthropic_model}"
            )
        return ComponentStatus(
            status="unconfigured", detail="ANTHROPIC_API_KEY not set"
        )
    if provider == "ollama":
        # Quick reachability check (sync-safe import of httpx)
        try:
            import httpx
            resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                return ComponentStatus(
                    status="ok",
                    detail=f"url={settings.ollama_base_url} model={settings.ollama_model}",
                )
            return ComponentStatus(status="degraded", detail=f"HTTP {resp.status_code}")
        except Exception as exc:
            return ComponentStatus(status="degraded", detail=str(exc))
    return ComponentStatus(status="error", detail=f"unknown provider: {provider}")
