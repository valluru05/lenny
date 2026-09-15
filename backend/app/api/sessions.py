"""
api/sessions.py — CRUD endpoints for ChatSession.

GET  /api/sessions         — list all sessions (newest first)
POST /api/sessions         — create a new session
GET  /api/sessions/{id}    — get session + message history
PATCH /api/sessions/{id}   — rename session
DELETE /api/sessions/{id}  — delete session + all messages + artifacts
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_db
from app.logging_conf import get_logger
from app.models import Artifact, ChatMessage, ChatSession
from app.schemas import (
    ArtifactOut,
    MessageOut,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    SourceChunk,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
log = get_logger("api.sessions")


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_session_or_404(session_id: str, db: AsyncSession) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


def _msg_to_out(msg: ChatMessage) -> MessageOut:
    """Convert ORM ChatMessage → MessageOut schema."""
    sources: list[SourceChunk] = []
    if msg.sources_json:
        try:
            raw = json.loads(msg.sources_json)
            sources = [SourceChunk(**s) for s in raw]
        except Exception:
            pass

    artifact_out: Optional[ArtifactOut] = None
    if msg.artifact:
        artifact_out = ArtifactOut.model_validate(msg.artifact)

    return MessageOut(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        skill=msg.skill,
        provider=msg.provider,
        model=msg.model,
        used_fallback=msg.used_fallback,
        is_grounded=msg.is_grounded,
        sources=sources,
        artifact=artifact_out,
        latency_ms=msg.latency_ms,
        created_at=msg.created_at,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
    result = await db.execute(
        select(ChatSession).order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [SessionOut.model_validate(s) for s in sessions]


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(
    body: SessionCreate, db: AsyncSession = Depends(get_db)
) -> SessionOut:
    session = ChatSession(title=body.title or "New Chat")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    log.info("session.created", session_id=session.id)
    return SessionOut.model_validate(session)


@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    """Return session metadata + full message history (with sources + artifacts)."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(
            selectinload(ChatSession.messages).selectinload(ChatMessage.artifact)
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "session": SessionOut.model_validate(session),
        "messages": [_msg_to_out(m) for m in session.messages],
    }


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: str,
    body: SessionUpdate,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    session = await _get_session_or_404(session_id, db)
    if body.title is not None:
        session.title = body.title
    await db.commit()
    await db.refresh(session)
    return SessionOut.model_validate(session)


@router.delete("/{session_id}", status_code=204, response_model=None)
async def delete_session(
    session_id: str, db: AsyncSession = Depends(get_db)
) -> None:
    session = await _get_session_or_404(session_id, db)
    await db.delete(session)
    await db.commit()
    log.info("session.deleted", session_id=session_id)
