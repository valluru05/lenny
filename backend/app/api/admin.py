"""
api/admin.py — Administrative endpoints (not user-facing).

POST /api/admin/reindex
  Rebuild the BM25 index from whatever transcripts are currently on disk.
  Demonstrates the "refreshed" part of the ingestion requirement:
  no service restart required — the new index is loaded into app.state
  immediately after building.

This endpoint is intentionally unprotected for the take-home demo.
In production, guard with an API key header or internal-network restriction.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import settings
from app.logging_conf import get_logger
from app.rag.index_store import IndexStore
from app.schemas import ReindexResponse

router = APIRouter(prefix="/admin", tags=["admin"])
log = get_logger("api.admin")


@router.post("/reindex", response_model=ReindexResponse)
async def reindex(request: Request) -> ReindexResponse:
    """
    Rebuild the BM25 index from disk transcripts and hot-swap it into app.state.
    Returns build statistics (episodes, chunks, duration).
    """
    log.info("admin.reindex_requested")

    store = IndexStore(settings.bm25_index_path)
    stats = store.build(settings.transcripts_dir)

    # Hot-swap into app.state — future requests use the new index immediately
    request.app.state.index_store = store

    log.info(
        "admin.reindex_done",
        episodes=stats["episodes_indexed"],
        chunks=stats["chunks_indexed"],
        duration_ms=stats["duration_ms"],
    )

    return ReindexResponse(
        status="ok",
        episodes_indexed=stats["episodes_indexed"],
        chunks_indexed=stats["chunks_indexed"],
        duration_ms=stats["duration_ms"],
    )
