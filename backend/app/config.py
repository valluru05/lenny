"""
config.py — All application settings driven by environment variables.
Uses pydantic-settings; no application code needs to import os.environ directly.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal, Optional, Union

from pydantic import Field, field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings  # type: ignore[assignment]
    SettingsConfigDict = dict  # type: ignore[misc,assignment]

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.dirname(_BACKEND_DIR)
_DEFAULT_DATA_DIR = os.path.join(_ROOT_DIR, "data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", os.path.join(_BACKEND_DIR, ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Lenny Growth Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite by default. Resolves to data/lenny.db if local.
    database_url: str = f"sqlite+aiosqlite:///{os.path.join(_DEFAULT_DATA_DIR, 'lenny.db')}"

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # Primary provider: "anthropic" | "ollama" | "mock"
    llm_provider: Literal["anthropic", "ollama", "mock"] = "mock"
    # Optional fallback tried if primary fails
    llm_fallback_provider: Optional[Literal["anthropic", "ollama", "mock"]] = None

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout: float = 120.0      # seconds; generous for local models

    # ── RAG ───────────────────────────────────────────────────────────────────
    transcripts_dir: str = os.path.join(_DEFAULT_DATA_DIR, "transcripts")
    bm25_index_path: str = os.path.join(_DEFAULT_DATA_DIR, "bm25_index.pkl")
    chunk_word_size: int = 200          # words per chunk
    chunk_overlap: int = 40             # words overlap between chunks
    retrieval_top_k: int = 8            # chunks returned per query
    retrieval_score_threshold: float = 15.5  # calibrated: topical~15.8-21, off-topic~13-15.3

    # ── Skills ────────────────────────────────────────────────────────────────
    ship30_min_words: int = 1100
    ship30_max_words: int = 1400
    ship30_min_headings: int = 3

    # ── Security ──────────────────────────────────────────────────────────────
    artifact_csp: str = (
        "default-src 'none'; "
        "script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; "
        "img-src data: https:; "
        "connect-src 'none';"
    )

    @field_validator("anthropic_api_key", "llm_fallback_provider", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Optional[str]:
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]


# Singleton — import this everywhere
settings = Settings()
