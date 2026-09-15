"""
api/chat.py — Main chat endpoint.

POST /api/sessions/{session_id}/chat

Flow:
  1. Persist user message to DB.
  2. Load conversation history (last N turns) for context.
  3. Get loaded IndexStore from app.state (or None if not built).
  4. Build LLMRouter (primary + fallback from config, or provider_override).
  5. Orchestrate → OrchestratorResult.
  6. Persist assistant message + artifact to DB.
  7. Return structured ChatResponse.

Error handling:
  - AllProvidersError → HTTP 503 with structured body (never a stack trace).
  - Session not found → HTTP 404.
  - Any other unexpected error → caught by global handler → HTTP 500.

POST /api/sessions/{session_id}/chat/regenerate
  Re-runs the last user turn with the alternate provider (compare feature).
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.orchestrator import orchestrate
from app.agent.router import AllProvidersError, LLMRouter
from app.api.sessions import _get_session_or_404, _msg_to_out
from app.deps import get_db
from app.logging_conf import get_logger
from app.models import Artifact, ChatMessage, ChatSession
from app.schemas import (
    ArtifactOut,
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    ErrorResponse,
    MessageOut,
)
from app.config import settings

router = APIRouter(tags=["chat"])
log = get_logger("api.chat")

# How many previous turns to include in context (each turn = 2 messages)
_HISTORY_TURNS = 6


async def _load_history(session_id: str, db: AsyncSession) -> list[dict]:
    """Return last N message turns as OpenAI-style dicts for the prompt."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(_HISTORY_TURNS * 2)
    )
    msgs = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs]


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: str,
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # ── Validate session ──────────────────────────────────────────────────────
    await _get_session_or_404(session_id, db)

    # ── Persist user message ──────────────────────────────────────────────────
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # ── Load history ──────────────────────────────────────────────────────────
    history = await _load_history(session_id, db)
    # Exclude the message we just added from history
    history = [h for h in history if h["content"] != body.message][-(_HISTORY_TURNS * 2):]

    # ── Get index ─────────────────────────────────────────────────────────────
    index = getattr(request.app.state, "index_store", None)

    # ── Build router ──────────────────────────────────────────────────────────
    router_inst = LLMRouter()

    # ── Orchestrate ───────────────────────────────────────────────────────────
    try:
        result = await orchestrate(
            user_message=body.message,
            index=index,
            router=router_inst,
            conversation_history=history,
            skill_override=body.skill,
            provider_override=body.provider_override,
        )
    except AllProvidersError as exc:
        log.error(
            "chat.all_providers_failed",
            session_id=session_id,
            primary=exc.primary_err,
            fallback=exc.fallback_err,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_unavailable",
                "message": "No LLM provider is currently available.",
                "primary_error": exc.primary_err,
                "fallback_error": exc.fallback_err,
            },
        )

    # ── Persist assistant message ─────────────────────────────────────────────
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=result.content,
        skill=result.skill,
        provider=result.provider,
        model=result.model,
        used_fallback=result.used_fallback,
        is_grounded=result.is_grounded,
        sources_json=result.sources_json,
        latency_ms=result.latency_ms,
    )
    db.add(assistant_msg)
    await db.flush()  # get ID before adding artifact

    # ── Persist artifact (if any) ─────────────────────────────────────────────
    artifact_row: Optional[Artifact] = None
    if result.artifact:
        artifact_row = Artifact(
            message_id=assistant_msg.id,
            kind=result.artifact.kind,
            title=result.artifact.title,
            content=result.artifact.content,
            sanitized=False,  # sanitization happens at render time in artifacts.py
        )
        db.add(artifact_row)

    await db.commit()
    await db.refresh(assistant_msg)
    if artifact_row:
        await db.refresh(artifact_row)

    # ── Update session title from first user message ──────────────────────────
    result2 = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session_obj = result2.scalar_one_or_none()
    if session_obj and session_obj.title == "New Chat":
        session_obj.title = body.message[:60]
        await db.commit()

    # ── Shape response ────────────────────────────────────────────────────────
    artifact_out: Optional[ArtifactOut] = None
    if artifact_row:
        artifact_out = ArtifactOut.model_validate(artifact_row)

    msg_out = MessageOut(
        id=assistant_msg.id,
        session_id=assistant_msg.session_id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        skill=assistant_msg.skill,
        provider=assistant_msg.provider,
        model=assistant_msg.model,
        used_fallback=assistant_msg.used_fallback,
        is_grounded=assistant_msg.is_grounded,
        sources=result.sources,
        artifact=artifact_out,
        latency_ms=assistant_msg.latency_ms,
        created_at=assistant_msg.created_at,
    )

    log.info(
        "chat.done",
        session_id=session_id,
        skill=result.skill,
        provider=result.provider,
        is_grounded=result.is_grounded,
        used_fallback=result.used_fallback,
        latency_ms=result.latency_ms,
    )

    return ChatResponse(message=msg_out)
