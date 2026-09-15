"""
agent/orchestrator.py — Skill routing + retrieval + provider calls + result shaping.

This is the custom lightweight orchestrator described in architecture.md.
It mirrors the core pattern of agent SDKs (system prompt, tool/retrieval calls,
skill routing, structured result) without binding to any specific provider.

Flow per request:
  1. Route: determine which skill to use (auto-detect or user-forced).
  2. Retrieve: query BM25 index → RetrievalResult (grounded / not-grounded).
  3. Skill: call the appropriate skill with the provider + retrieval result.
  4. Persist: (done by the API layer, not here — keeps orchestrator pure).
  5. Shape: return a structured OrchestratorResult.

Skill routing (auto mode):
  - "artifact", "html", "generate a doc", "markdown" in message → artifact
  - "essay", "ship 30", "write about", "blog post" in message → ship30_essay
  - everything else → qa
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional

from app.agent.providers.base import CompletionResponse
from app.agent.router import AllProvidersError, LLMRouter
from app.agent.skills.artifact_skill import ExtractedArtifact
from app.config import settings
from app.logging_conf import get_logger
from app.rag.retriever import RetrievalResult, retrieve
from app.schemas import SourceChunk

if TYPE_CHECKING:
    from app.rag.index_store import IndexStore

log = get_logger("orchestrator")

SkillName = Literal["qa", "ship30_essay", "artifact"]

# Keywords that trigger specific skills in auto-routing
_ARTIFACT_KEYWORDS = re.compile(
    r"\b(artifact"
    r"|generate.*(html|page|dashboard|calculator|tool|app|doc|document|markdown)"
    r"|create.*(html|page|dashboard|calculator|tool|app|doc|document|markdown)"
    r"|build.*(html|page|dashboard|calculator|tool|app|doc|document|markdown)"
    r"|make.*(html|page|dashboard|calculator|tool|app|doc|document|markdown)"
    r"|html\s+(page|code|doc|document|dashboard|calculator|tool|app|artifact)?"
    r"|dashboard"
    r"|calculator"
    r"|interactive\s+app"
    r"|web\s+app"
    r"|markdown\s+(doc|document|artifact|page)"
    r"|render\s+(a\s+)?(page|doc|document))\b",
    re.IGNORECASE,
)
_ESSAY_KEYWORDS = re.compile(
    r"\b(essay|ship\s*30|write\s+(a\s+)?(blog|post|article|newsletter)|"
    r"write\s+about|blog\s+post|newsletter)\b",
    re.IGNORECASE,
)


def route_skill(message: str, forced: Optional[str] = None) -> SkillName:
    """Determine which skill to use for this message."""
    if forced and forced != "auto":
        return forced  # type: ignore[return-value]
    if _ARTIFACT_KEYWORDS.search(message):
        return "artifact"
    if _ESSAY_KEYWORDS.search(message):
        return "ship30_essay"
    return "qa"


# ── Result object ─────────────────────────────────────────────────────────────

@dataclass
class OrchestratorResult:
    content: str
    skill: SkillName
    provider: str
    model: str
    used_fallback: bool
    is_grounded: bool
    sources: list[SourceChunk] = field(default_factory=list)
    artifact: Optional[ExtractedArtifact] = None
    latency_ms: int = 0
    sources_json: str = "[]"    # pre-serialised for DB storage


# ── Main entry point ──────────────────────────────────────────────────────────

async def orchestrate(
    user_message: str,
    index: Optional["IndexStore"],
    router: LLMRouter,
    conversation_history: Optional[list[dict]] = None,
    skill_override: Optional[str] = None,
    provider_override: Optional[str] = None,
) -> OrchestratorResult:
    """
    Orchestrate a single user turn end-to-end.

    Args:
        user_message:         The user's raw text input.
        index:                Loaded IndexStore (or None if not built yet).
        router:               LLMRouter instance (primary + fallback).
        conversation_history: List of {"role", "content"} dicts for context.
        skill_override:       "qa" | "ship30_essay" | "artifact" | "auto" | None
        provider_override:    Force a specific provider for this request (compare feature).

    Returns:
        OrchestratorResult with all fields populated.

    Raises:
        AllProvidersError: if both primary and fallback providers fail.
    """
    t0 = time.perf_counter()

    # ── 1. Route ──────────────────────────────────────────────────────────────
    skill = route_skill(user_message, forced=skill_override)
    log.info("orchestrator.start", skill=skill, query=user_message[:80])

    # ── 2. Retrieve ───────────────────────────────────────────────────────────
    if index is not None and index.is_loaded():
        retrieval = retrieve(user_message, index)
    else:
        log.warning("orchestrator.no_index", skill=skill)
        retrieval = RetrievalResult(is_grounded=False, sources=[], context_text="")

    # ── 3. Select provider ────────────────────────────────────────────────────
    if provider_override:
        from app.agent.router import _build_provider
        from app.agent.providers.base import CompletionRequest
        try:
            provider = _build_provider(provider_override)
        except Exception as exc:
            log.warning("orchestrator.provider_override_failed", exc=str(exc))
            provider = router._get_primary()
    else:
        provider = router._get_primary()

    # ── 4. Execute skill ──────────────────────────────────────────────────────
    artifact: Optional[ExtractedArtifact] = None
    completion: CompletionResponse

    try:
        if skill == "artifact":
            from app.agent.skills import artifact_skill
            completion, artifact = await artifact_skill.run(
                user_message, retrieval, provider, conversation_history
            )
        elif skill == "ship30_essay":
            from app.agent.skills import ship30_skill
            from app.agent.skills.qa_skill import NOT_GROUNDED_PREFIX
            completion = await ship30_skill.run(
                user_message, retrieval, provider, conversation_history
            )
            if not completion.content.startswith(NOT_GROUNDED_PREFIX):
                title_match = re.search(r"^#+\s+(.+)$", completion.content, re.MULTILINE)
                essay_title = title_match.group(1).strip() if title_match else f"Essay: {user_message[:40]}"
                artifact = ExtractedArtifact(
                    title=essay_title,
                    kind="markdown",
                    content=completion.content,
                )
        else:
            from app.agent.skills import qa_skill
            from app.agent.skills.artifact_skill import extract_artifact
            completion = await qa_skill.run(
                user_message, retrieval, provider, conversation_history
            )
            # Auto-extract artifact if QA response contains an HTML or markdown tool
            possible_art = extract_artifact(completion.content)
            if possible_art:
                artifact = possible_art

    except Exception as primary_exc:
        # If the direct provider call failed and there's a fallback in the router, retry
        if provider_override:
            raise  # don't retry for explicit override requests
        log.warning("orchestrator.skill_error_retrying_via_router", exc=str(primary_exc))
        # Re-run through the router (which has fallback logic)
        from app.agent.providers.base import CompletionRequest
        req = CompletionRequest(
            messages=[{"role": "user", "content": user_message}],
            max_tokens=2048,
        )
        completion = await router.complete(req)
        artifact = None

    # ── 5. Determine grounding ────────────────────────────────────────────────
    from app.agent.skills.qa_skill import NOT_GROUNDED_PREFIX
    content = completion.content

    # Strip internal tag before storing
    is_grounded: bool
    if content.startswith(NOT_GROUNDED_PREFIX):
        is_grounded = False
        content = content[len(NOT_GROUNDED_PREFIX):].lstrip()
    else:
        is_grounded = retrieval.is_grounded

    # ── 6. Shape result ───────────────────────────────────────────────────────
    latency_ms = int((time.perf_counter() - t0) * 1000)

    log.info(
        "orchestrator.done",
        skill=skill,
        provider=completion.provider,
        model=completion.model,
        is_grounded=is_grounded,
        sources=len(retrieval.sources),
        used_fallback=completion.used_fallback,
        latency_ms=latency_ms,
    )

    return OrchestratorResult(
        content=content,
        skill=skill,
        provider=completion.provider,
        model=completion.model,
        used_fallback=completion.used_fallback,
        is_grounded=is_grounded,
        sources=retrieval.sources,
        artifact=artifact,
        latency_ms=latency_ms,
        sources_json=json.dumps([s.model_dump() for s in retrieval.sources]),
    )
