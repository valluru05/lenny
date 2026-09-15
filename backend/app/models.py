"""
models.py — SQLAlchemy ORM models.

Tables:
  chat_sessions   — one row per user conversation (independent context)
  chat_messages   — one row per turn; carries skill, provider, sources, latency
  artifacts       — generated Markdown/HTML documents stored per message
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))        # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    skill: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)   # qa | ship30_essay | artifact
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    sources_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of source dicts
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_grounded: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
    artifact: Mapped[Optional["Artifact"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), unique=True
    )
    kind: Mapped[str] = mapped_column(String(16))        # "markdown" | "html"
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)           # raw source (before sanitization)
    sanitized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    message: Mapped["ChatMessage"] = relationship(back_populates="artifact")
