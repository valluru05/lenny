"""
api/artifacts.py — Artifact fetch + rendered output endpoints.

GET /api/artifacts/{artifact_id}        — raw artifact detail (source + rendered)
GET /api/artifacts/{artifact_id}/render — serve the rendered/wrapped HTML directly

Security (documented in architecture.md):
  - Markdown artifacts: rendered to HTML server-side (markdown-it-py),
    then allowlist-sanitized with bleach before ever reaching the browser.
    Safe to inject inline — no scripts, no event handlers, no dangerous URLs.

  - Raw HTML artifacts: do NOT strip scripts/styles — a self-contained
    HTML artifact legitimately needs its own script to be useful.
    Instead, the client renders it inside:
      <iframe sandbox="allow-scripts" srcdoc="...">
    with NO allow-same-origin, so any script in the artifact cannot read
    cookies/localStorage/parent DOM or call the backend with the user's session.
    We also inject a strict CSP meta tag as defence-in-depth to block
    outbound network calls from within the iframe.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.logging_conf import get_logger
from app.models import Artifact
from app.schemas import ArtifactDetail

router = APIRouter(prefix="/artifacts", tags=["artifacts"])
log = get_logger("api.artifacts")


async def _get_artifact_or_404(artifact_id: str, db: AsyncSession) -> Artifact:
    result = await db.execute(
        select(Artifact).where(Artifact.id == artifact_id)
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found")
    return artifact


def _render_artifact(artifact: Artifact) -> str:
    """
    Produce the rendered HTML string for an artifact.
    For markdown: bleach-sanitized HTML (safe to inline).
    For html: iframe srcdoc wrapper with CSP (sandboxed).
    """
    from app.security.sanitize import render_markdown, wrap_html_artifact
    if artifact.kind == "markdown":
        return render_markdown(artifact.content)
    else:
        return wrap_html_artifact(artifact.content)


@router.get("/{artifact_id}", response_model=ArtifactDetail)
async def get_artifact(
    artifact_id: str, db: AsyncSession = Depends(get_db)
) -> ArtifactDetail:
    artifact = await _get_artifact_or_404(artifact_id, db)
    rendered = _render_artifact(artifact)

    return ArtifactDetail(
        id=artifact.id,
        message_id=artifact.message_id,
        kind=artifact.kind,
        title=artifact.title,
        content=artifact.content,
        rendered=rendered,
        sanitized=artifact.kind == "markdown",  # markdown gets sanitized; html gets sandboxed
        created_at=artifact.created_at,
    )


@router.get("/{artifact_id}/render", response_class=HTMLResponse)
async def render_artifact_direct(
    artifact_id: str, db: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    """Serve the rendered artifact as a standalone HTML response."""
    artifact = await _get_artifact_or_404(artifact_id, db)
    rendered = _render_artifact(artifact)
    return HTMLResponse(content=rendered)
