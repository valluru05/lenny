"""
rag/chunker.py — Parse transcript files and split into overlapping word-window chunks.

Each chunk carries full back-reference metadata so every retrieved chunk can be
cited in the UI:
  - guest, title, episode_slug, youtube_url, publish_date, keywords
  - chunk_index (position within episode)
  - text (the actual words)

Chunking strategy:
  - Strip YAML frontmatter, skip the H1 title line, keep speaker-turn content.
  - Slide a fixed-size word window with overlap (configurable via settings).
  - This preserves conversational context while keeping chunks small enough
    for a concise LLM prompt.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from app.config import settings
from app.logging_conf import get_logger

log = get_logger("rag.chunker")


@dataclass
class Chunk:
    """A single retrievable unit from a transcript."""
    episode_slug: str
    guest: str
    title: str
    youtube_url: str
    publish_date: str
    keywords: list[str]
    chunk_index: int
    text: str

    @property
    def snippet(self) -> str:
        """First 300 chars — shown in the Sources panel."""
        return self.text[:300].rstrip() + ("…" if len(self.text) > 300 else "")


# ── Frontmatter parsing ───────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_without_frontmatter)."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    meta = yaml.safe_load(m.group(1)) or {}
    body = content[m.end():]
    return meta, body


def _clean_body(body: str) -> str:
    """
    Remove markdown headings (# / ##), speaker timestamps like (00:01:23),
    and collapse multiple blank lines.  Keeps the spoken words only.
    """
    # Drop H1/H2 headings
    body = re.sub(r"^#{1,2} .+$", "", body, flags=re.MULTILINE)
    # Drop timestamps like (00:01:23)
    body = re.sub(r"\(\d{2}:\d{2}:\d{2}\)", "", body)
    # Collapse whitespace
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


# ── Word-window chunking ──────────────────────────────────────────────────────

def _word_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping word windows."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += size - overlap
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_episode(path: Path) -> list[Chunk]:
    """Parse a single transcript.md file and return its chunks."""
    content = path.read_text(encoding="utf-8", errors="replace")
    meta, body = _parse_frontmatter(content)

    guest = meta.get("guest", "Unknown")
    title = meta.get("title", path.parent.name)
    youtube_url = meta.get("youtube_url", "")
    publish_date = str(meta.get("publish_date", ""))
    keywords = meta.get("keywords", []) or []
    episode_slug = path.parent.name

    body = _clean_body(body)
    raw_chunks = _word_chunks(body, settings.chunk_word_size, settings.chunk_overlap)

    chunks = [
        Chunk(
            episode_slug=episode_slug,
            guest=guest,
            title=title,
            youtube_url=youtube_url,
            publish_date=publish_date,
            keywords=keywords,
            chunk_index=i,
            text=text,
        )
        for i, text in enumerate(raw_chunks)
        if text.strip()
    ]
    return chunks


def chunk_all_episodes(transcripts_dir: Optional[str] = None) -> list[Chunk]:
    """Walk transcripts_dir, chunk every transcript.md, return all chunks."""
    base = Path(transcripts_dir or settings.transcripts_dir)
    all_chunks: list[Chunk] = []
    episode_dirs = sorted(p for p in base.iterdir() if p.is_dir())

    log.info("chunker.start", episodes=len(episode_dirs), base=str(base))

    for ep_dir in episode_dirs:
        transcript_file = ep_dir / "transcript.md"
        if not transcript_file.exists():
            log.debug("chunker.skip", slug=ep_dir.name, reason="no transcript.md")
            continue
        try:
            chunks = chunk_episode(transcript_file)
            all_chunks.extend(chunks)
        except Exception as exc:
            log.warning("chunker.error", slug=ep_dir.name, exc=str(exc))

    log.info("chunker.done", total_chunks=len(all_chunks))
    return all_chunks
