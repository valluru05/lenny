"""
schemas.py — Pydantic request/response contracts for all API surfaces.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ── Health ─────────────────────────────────────────────────────────────────

class ComponentStatus(BaseModel):
    status: Literal["ok", "degraded", "error", "unconfigured"]
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    version: str
    components: dict[str, ComponentStatus]


# ── Sessions ───────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class SessionOut(BaseModel):
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Sources ────────────────────────────────────────────────────────────────

class SourceChunk(BaseModel):
    """One retrieved transcript chunk included in a grounded response."""
    guest: str
    title: str
    episode_slug: str
    youtube_url: str
    snippet: str               # ~first 300 chars of the chunk
    score: float


# ── Chat ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    skill: Optional[Literal["auto", "qa", "ship30_essay", "artifact"]] = "auto"
    # Force a specific provider for this request (e.g. "compare providers" feature)
    provider_override: Optional[Literal["anthropic", "ollama", "mock"]] = None


class ArtifactOut(BaseModel):
    id: str
    kind: Literal["markdown", "html"]
    title: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    skill: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    used_fallback: bool
    is_grounded: Optional[bool]
    sources: list[SourceChunk] = []
    artifact: Optional[ArtifactOut] = None
    latency_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    message: MessageOut


# ── Artifacts ──────────────────────────────────────────────────────────────

class ArtifactDetail(BaseModel):
    id: str
    message_id: str
    kind: Literal["markdown", "html"]
    title: Optional[str]
    content: str              # raw source
    rendered: str             # sanitized HTML (markdown) or iframe srcdoc wrapper (html)
    sanitized: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Admin ──────────────────────────────────────────────────────────────────

class ReindexResponse(BaseModel):
    status: str
    episodes_indexed: int
    chunks_indexed: int
    duration_ms: int


# ── Error ──────────────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
