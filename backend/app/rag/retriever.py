"""
rag/retriever.py — Query the BM25 index and decide grounded vs. ungrounded.

Grounding logic:
  - If the top result's score is below `settings.retrieval_score_threshold`,
    the retriever sets `is_grounded=False` and returns empty sources.
  - The QA skill checks this flag and uses an explicit "not enough evidence"
    path instead of guessing — the assistant never silently hallucinates.
  - This threshold is tunable in config without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from app.config import settings
from app.logging_conf import get_logger
from app.rag.chunker import Chunk
from app.schemas import SourceChunk

if TYPE_CHECKING:
    from app.rag.index_store import IndexStore

log = get_logger("rag.retriever")


@dataclass
class RetrievalResult:
    is_grounded: bool          # True if top score ≥ threshold
    sources: list[SourceChunk] # Empty when not grounded
    context_text: str          # Concatenated chunk texts for the LLM prompt


def retrieve(
    query: str,
    index: "IndexStore",
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
) -> RetrievalResult:
    """
    Search the BM25 index for `query`.
    Returns a RetrievalResult with grounding decision + source chunks.
    """
    k = top_k or settings.retrieval_top_k
    threshold = score_threshold if score_threshold is not None else settings.retrieval_score_threshold

    if not index.is_loaded():
        log.warning("retriever.index_not_loaded")
        return RetrievalResult(is_grounded=False, sources=[], context_text="")

    ranked = index.search(query, top_k=k)

    if not ranked:
        log.info("retriever.no_results", query=query[:80])
        return RetrievalResult(is_grounded=False, sources=[], context_text="")

    top_score = ranked[0][1]
    is_grounded = top_score >= threshold

    log.info(
        "retriever.search",
        query=query[:80],
        top_score=round(top_score, 3),
        is_grounded=is_grounded,
        results=len(ranked),
    )

    if not is_grounded:
        return RetrievalResult(is_grounded=False, sources=[], context_text="")

    # Build source list and context block for the prompt
    sources: list[SourceChunk] = []
    context_parts: list[str] = []

    for chunk, score in ranked:
        sources.append(
            SourceChunk(
                guest=chunk.guest,
                title=chunk.title,
                episode_slug=chunk.episode_slug,
                youtube_url=chunk.youtube_url,
                snippet=chunk.snippet,
                score=round(score, 4),
            )
        )
        context_parts.append(
            f"[Source: {chunk.guest} — {chunk.title}]\n{chunk.text}"
        )

    context_text = "\n\n---\n\n".join(context_parts)
    return RetrievalResult(
        is_grounded=True,
        sources=sources,
        context_text=context_text,
    )
