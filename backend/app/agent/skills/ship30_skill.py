"""
agent/skills/ship30_skill.py — Ship 30 for 30 essay skill.

Generates a structured ~1,250-word essay grounded in transcript excerpts,
following the Ship 30 for 30 writing principles:
  https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide

Writing contract enforced:
  - ~1,100–1,400 words
  - Strong hook (first line pulls the reader in, no preamble)
  - Clear narrative: Hook → Tension → Insight → Mechanics → Takeaway
  - Skimmable formatting: ≥3 headings, bullet points, selective bold
  - One specific, useful takeaway at the end
  - All claims grounded in the provided transcript excerpts

Self-check loop (agentic behaviour):
  After generation, validate() checks the essay against the contract.
  If it fails, we send one automatic revision prompt with specific
  feedback. This "self-check → revision" loop is a real agentic
  behaviour — demonstrable in the demo video as the assistant
  correcting its own output, not just a static prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agent.providers.base import CompletionRequest, CompletionResponse
from app.config import settings
from app.logging_conf import get_logger
from app.rag.retriever import RetrievalResult

if TYPE_CHECKING:
    from app.agent.providers.base import LLMProvider

log = get_logger("skill.ship30")

# ── Prompts ──────────────────────────────────────────────────────────────────

_ESSAY_SYSTEM = """You are an expert online writer who follows the Ship 30 for 30 framework.

Write a ~1,250-word essay (strictly between 1,100 and 1,400 words) on the topic the user specifies.
Ground every insight and claim in the transcript excerpts provided below.

STRICT WRITING RULES:
1. HOOK (first 1-3 lines): Start with a bold, provocative, or counter-intuitive statement.
   NO preamble like "In this essay..." or "Today I want to talk about..."
   The very first word must pull the reader in.
2. STRUCTURE: Hook → Tension (the problem) → Insight (what the transcripts reveal) 
   → Mechanics (the how) → Takeaway (one actionable conclusion)
3. FORMATTING: Use ## headings (at least 3), bullet points, and **bold** for key phrases.
4. LENGTH: Target 1,250 words. Never go below 1,100 or above 1,400.
5. CITATIONS: Reference guests by name (e.g., "As Adam Fishman explained...").
6. END with a section called "## The One Thing" containing a single, specific takeaway.

TRANSCRIPT EXCERPTS:
{context}
"""

_REVISION_SYSTEM = """You are a writing editor reviewing a Ship 30 for 30 essay.

The essay below failed its quality check. Fix the specific issues listed and rewrite the full essay.
Keep all the grounding and citations. Do not add new information not in the original.

ISSUES TO FIX:
{issues}

ORIGINAL ESSAY:
{essay}

Rewrite the complete essay now, fixing all listed issues. The essay MUST be between 1,100 and 1,400 words.
"""


# ── Validation ────────────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    passed: bool
    word_count: int
    issues: list[str]


def validate(essay: str) -> ValidationResult:
    """
    Programmatic self-check against the Ship 30 writing contract.
    Returns a ValidationResult with any violations listed.
    This is the validation step of the self-check loop.
    """
    issues: list[str] = []

    # 1. Word count
    words = essay.split()
    word_count = len(words)
    if word_count < settings.ship30_min_words:
        issues.append(
            f"Essay is too short ({word_count} words). Target 1,100–1,400 words."
        )
    elif word_count > settings.ship30_max_words:
        issues.append(
            f"Essay is too long ({word_count} words). Target 1,100–1,400 words."
        )

    # 2. Heading count (## or ###)
    headings = re.findall(r"^#{2,3}\s+.+", essay, re.MULTILINE)
    if len(headings) < settings.ship30_min_headings:
        issues.append(
            f"Only {len(headings)} headings found. Need at least {settings.ship30_min_headings} (##)."
        )

    # 3. Bullet points present
    bullets = re.findall(r"^\s*[-*]\s+", essay, re.MULTILINE)
    if not bullets:
        issues.append("No bullet points found. Add at least one bullet list for scannability.")

    # 4. Bold text present
    bold = re.findall(r"\*\*.+?\*\*", essay)
    if not bold:
        issues.append("No bold text found. Use **bold** to highlight key phrases.")

    # 5. Hook check — first line should not start with "In ", "Today", "This essay"
    first_line = essay.strip().split("\n")[0].lstrip("#").strip()
    preamble_patterns = [
        r"^in this",
        r"^today i",
        r"^this essay",
        r"^in today",
        r"^welcome to",
        r"^let me ",
        r"^i want to",
    ]
    for pat in preamble_patterns:
        if re.match(pat, first_line.lower()):
            issues.append(
                f"Weak hook: first line starts with preamble ({first_line[:60]!r}). "
                "Start with a strong statement, question, or counter-intuitive claim."
            )
            break

    # 6. "The One Thing" takeaway section
    if "the one thing" not in essay.lower():
        issues.append('Missing final section "## The One Thing" with a single actionable takeaway.')

    passed = len(issues) == 0
    log.info(
        "ship30.validate",
        passed=passed,
        word_count=word_count,
        headings=len(headings),
        bullets=len(bullets),
        bold_phrases=len(bold),
        issues=len(issues),
    )
    return ValidationResult(passed=passed, word_count=word_count, issues=issues)


# ── Main skill entry point ────────────────────────────────────────────────────

async def run(
    user_message: str,
    retrieval: RetrievalResult,
    provider: "LLMProvider",
    conversation_history: list[dict] | None = None,
) -> CompletionResponse:
    """
    Execute the Ship 30 essay skill with one automatic revision pass if needed.

    Flow:
      1. Generate essay from transcript context.
      2. validate() checks the writing contract.
      3. If failed: send revision prompt with specific issues → one more attempt.
      4. Return the (possibly revised) essay.

    The revision attempt is logged so the demo video can show it happening.
    """
    if not retrieval.is_grounded:
        # Can't write a grounded essay without sources
        log.warning("ship30.not_grounded", query=user_message[:60])
        from app.agent.skills.qa_skill import NOT_GROUNDED_PREFIX
        mock_resp = CompletionResponse(
            content=(
                f"{NOT_GROUNDED_PREFIX}\n\n"
                "I couldn't find relevant transcript content to ground a Ship 30 essay on this topic. "
                "Please ask about a topic covered in Lenny's Podcast (growth, onboarding, PMF, "
                "pricing, retention, leadership, etc.)."
            ),
            provider=provider.name,
            model=provider.model,
        )
        return mock_resp

    system = _ESSAY_SYSTEM.format(context=retrieval.context_text)
    history = conversation_history or []

    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            f"Write a Ship 30 for 30 essay on: {user_message}\n\n"
            "Remember: strong hook first, 1,100–1,400 words, ≥3 headings, "
            "bullets, bold, end with '## The One Thing'."
        ),
    })

    # ── Pass 1: initial generation ───────────────────────────────────────────
    log.info("ship30.generating", query=user_message[:60])
    response = await provider.complete(
        CompletionRequest(messages=messages, max_tokens=3000, temperature=0.6)
    )

    result = validate(response.content)

    if result.passed:
        log.info("ship30.passed_first_pass", word_count=result.word_count)
        return response

    # ── Pass 2: automatic revision ────────────────────────────────────────────
    issues_text = "\n".join(f"- {issue}" for issue in result.issues)
    log.info(
        "ship30.revision_needed",
        issues=len(result.issues),
        word_count=result.word_count,
    )

    revision_messages = [
        {
            "role": "system",
            "content": _REVISION_SYSTEM.format(
                issues=issues_text,
                essay=response.content,
            ),
        },
        {"role": "user", "content": "Please rewrite the essay fixing all listed issues."},
    ]

    revised_response = await provider.complete(
        CompletionRequest(messages=revision_messages, max_tokens=3000, temperature=0.5)
    )

    revised_result = validate(revised_response.content)
    log.info(
        "ship30.revision_done",
        passed=revised_result.passed,
        word_count=revised_result.word_count,
        remaining_issues=len(revised_result.issues),
    )

    # Append revision metadata to content so the UI can show it happened
    if not revised_result.passed:
        note = (
            f"\n\n---\n*Note: This essay was automatically revised. "
            f"Remaining issues: {'; '.join(revised_result.issues)}*"
        )
        revised_response.content += note

    return revised_response
