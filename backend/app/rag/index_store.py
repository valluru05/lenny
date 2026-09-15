"""
rag/index_store.py — BM25 index backed by rank_bm25.

Design decisions:
  - Pure-Python BM25 (rank_bm25.BM25Okapi) — fully offline, no embedding model,
    no network dependency, no cold-start download.
  - Index is serialized to disk (pickle) so it survives restarts without rebuilding.
  - Rebuild triggered via POST /api/admin/reindex — no service restart required.
  - This is a documented swappable component: a future iteration can drop in a
    vector index (e.g. FAISS + sentence-transformers) by implementing the same
    IndexStore interface without touching the rest of the pipeline.
"""
from __future__ import annotations

import os
import pickle
import re
import time
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from app.logging_conf import get_logger
from app.rag.chunker import Chunk, chunk_all_episodes

log = get_logger("rag.index_store")

# Simple tokenizer — lowercase + split on non-word chars
_TOKEN_RE = re.compile(r"\W+")


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.split(text.lower()) if t]


class IndexStore:
    """
    Wraps BM25Okapi + the original chunk list.
    Call build() to create a new index; save()/load() to persist to disk.
    """

    def __init__(self, index_path: str) -> None:
        self._path = Path(index_path)
        self._bm25: Optional[BM25Okapi] = None
        self._chunks: list[Chunk] = []

    # ── Public interface ──────────────────────────────────────────────────────

    def exists(self) -> bool:
        return self._path.exists()

    def is_loaded(self) -> bool:
        return self._bm25 is not None

    def build(self, transcripts_dir: Optional[str] = None) -> dict:
        """Build the index from disk transcripts. Returns build stats."""
        t0 = time.perf_counter()

        chunks = chunk_all_episodes(transcripts_dir)
        if not chunks:
            raise ValueError("No chunks produced — check transcripts_dir path")

        tokenized = [_tokenize(c.text) for c in chunks]
        bm25 = BM25Okapi(tokenized)

        self._chunks = chunks
        self._bm25 = bm25

        self.save()

        duration_ms = int((time.perf_counter() - t0) * 1000)
        # count unique episodes
        episodes = len({c.episode_slug for c in chunks})
        log.info(
            "index.built",
            episodes=episodes,
            chunks=len(chunks),
            duration_ms=duration_ms,
        )
        return {
            "episodes_indexed": episodes,
            "chunks_indexed": len(chunks),
            "duration_ms": duration_ms,
        }

    def save(self) -> None:
        """Persist index + chunks to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "chunks": self._chunks}, f)
        log.info("index.saved", path=str(self._path))

    def load(self) -> None:
        """Load a previously built index from disk."""
        with open(self._path, "rb") as f:
            data = pickle.load(f)
        self._bm25 = data["bm25"]
        self._chunks = data["chunks"]
        log.info(
            "index.loaded",
            chunks=len(self._chunks),
            path=str(self._path),
        )

    def search(self, query: str, top_k: int = 8) -> list[tuple[Chunk, float]]:
        """
        Return top_k (chunk, score) pairs sorted by BM25 score descending.
        Score is raw BM25 — higher is more relevant.
        Returns [] if index not loaded.
        """
        if self._bm25 is None or not self._chunks:
            log.warning("index.search_on_empty_index")
            return []

        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)

        # Pair with chunks, sort descending
        ranked = sorted(
            zip(self._chunks, scores.tolist()),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]
