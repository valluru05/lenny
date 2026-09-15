"""
agent/skills/qa_skill.py — Grounded Q&A skill.

Behaviour:
  - If retrieval returns is_grounded=True: answer strictly from the transcript
    context, cite sources, never add unsupported claims.
  - If retrieval returns is_grounded=False: return an explicit "not enough
    evidence" answer — the UI renders this distinctly (no fabricated confidence).
    The assistant NEVER silently hallucinates.

The system prompt encodes this as a hard constraint, not a soft preference,
so even a model prone to hallucination is guided toward the correct behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agent.providers.base import CompletionRequest, CompletionResponse
from app.config import settings
from app.logging_conf import get_logger
from app.rag.retriever import RetrievalResult

if TYPE_CHECKING:
    from app.agent.providers.base import LLMProvider

log = get_logger("skill.qa")

_QA_SYSTEM_GROUNDED = """You are the Lenny Growth Assistant — an expert on product management and growth strategy.

You answer questions STRICTLY from the transcript excerpts provided below. Rules:
1. Only use information present in the provided transcripts. Do not add outside knowledge.
2. Always cite the guest and episode when you use their words or ideas.
3. If multiple sources say different things, acknowledge the nuance.
4. Write in a clear, direct style. Use bullet points where helpful.
5. End with a one-line "Key takeaway:" summary.

If the transcripts don't fully answer the question, say so explicitly — do not guess or pad with generic advice.

TRANSCRIPT EXCERPTS:
{context}
"""

_QA_SYSTEM_UNGROUNDED = """You are the Lenny Growth Assistant.

The user asked a question that is NOT covered by Lenny's Podcast transcripts in the knowledge base.
You must be honest about this. Do NOT fabricate an answer.

Respond with a short, clear message explaining:
1. That you couldn't find relevant content in the transcripts for this question.
2. What kinds of questions ARE in the knowledge base (product management, growth strategy, 
   startup scaling, onboarding, pricing, PMF, retention, leadership, etc.).
3. Suggest a related question they could ask that you could answer from the transcripts.

Keep it brief and helpful — under 100 words.
"""

NOT_GROUNDED_PREFIX = "⚠️ NOT_GROUNDED"


async def run(
    user_message: str,
    retrieval: RetrievalResult,
    provider: "LLMProvider",
    conversation_history: list[dict] | None = None,
) -> CompletionResponse:
    """
    Execute the QA skill.
    Returns a CompletionResponse whose content is the assistant's answer.
    The is_grounded flag is already in the RetrievalResult — the orchestrator
    persists it to the DB so the UI can render it differently.
    """
    history = conversation_history or []

    if retrieval.is_grounded:
        system = _QA_SYSTEM_GROUNDED.format(context=retrieval.context_text)
        log.info("qa.grounded", sources=len(retrieval.sources), query=user_message[:60])
    else:
        system = _QA_SYSTEM_UNGROUNDED
        log.info("qa.not_grounded", query=user_message[:60])

    # Build message list: system + conversation history + current user turn
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = await provider.complete(
        CompletionRequest(messages=messages, max_tokens=2048, temperature=0.4)
    )

    # Tag ungrounded responses so the orchestrator can flag them
    if not retrieval.is_grounded:
        response.content = f"{NOT_GROUNDED_PREFIX}\n\n{response.content}"

    return response
