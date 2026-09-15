"""
agent/skills/artifact_skill.py — Artifact generation skill.

Extracts a single fenced code block from the model's output:
  - ```markdown ... ``` → kind="markdown"
  - ```html ... ```     → kind="html"

The extracted content is stored as a raw Artifact row. The security
layer (Phase 6) handles sanitization before rendering:
  - Markdown artifacts: rendered to HTML via markdown-it, then
    allowlist-sanitized with bleach before the browser sees it.
  - HTML artifacts: NOT stripped — a self-contained HTML artifact
    legitimately needs its <script>/<style>. Instead, isolated at
    render time inside <iframe sandbox="allow-scripts" srcdoc="...">.

Title derivation:
  - For markdown: first H1 or H2 heading in the extracted content.
  - For HTML: <title> tag content.
  - Fallback: first 60 chars of the user message.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from app.agent.providers.base import CompletionRequest, CompletionResponse
from app.logging_conf import get_logger
from app.rag.retriever import RetrievalResult

if TYPE_CHECKING:
    from app.agent.providers.base import LLMProvider

log = get_logger("skill.artifact")

_ARTIFACT_SYSTEM = """You are an expert technical writer and senior frontend developer.

The user wants to generate an interactive application, calculator, dashboard, or structured document.
Create exactly ONE complete, self-contained deliverable:

For HTML artifacts:
- Produce a complete, stunning, single-page application (DOCTYPE, head, style, body, script).
- Include rich modern CSS inline in <style>: dark mode theme (#0b0f19 background, #151d30 cards, #38bdf8 sky blue and #10b981 emerald accents, glowing borders, font-family 'Inter' or system-ui).
- Include KPI metric cards (e.g. Total Revenue, Retention Rate, Orders, Conversion Rate).
- Include interactive controls (input fields, sliders, calculate buttons, real-time formula computation).
- Wrap it in a fenced code block: ```html ... ```

For MARKDOWN artifacts:
- Produce a well-structured document with # H1 title, ## headings, bullet points, and key takeaways.
- Wrap it in a fenced code block: ```markdown ... ```

IMPORTANT: Output ONLY the fenced code block. No conversational preamble before or after.
The artifact must be 100% complete, fully styled, interactive, and renderable as-is.

CONTEXT FROM TRANSCRIPTS:
{context}
"""

_ARTIFACT_USER_TEMPLATE = """Generate a comprehensive {kind} artifact for: {topic}

Requirements: {requirements}"""

# ── Fence extraction ──────────────────────────────────────────────────────────

_FENCE_RE = re.compile(
    r"```([a-zA-Z0-9_-]*)\s*\n(.*?)```",
    re.DOTALL,
)


@dataclass
class ExtractedArtifact:
    kind: str           # "markdown" | "html"
    content: str        # raw source
    title: Optional[str]


def extract_artifact(model_output: str) -> Optional[ExtractedArtifact]:
    """
    Find fenced code blocks or raw HTML/Markdown in model_output.
    Returns None only if no renderable content found.
    """
    # 1. Search for fenced blocks (```html, ```markdown, or generic ```)
    fences = list(_FENCE_RE.finditer(model_output))
    for match in fences:
        lang = match.group(1).lower()
        block = match.group(2).strip()
        if not block:
            continue
        if lang in ("html", "htm", "xml") or "<!doctype html" in block.lower() or "<html" in block.lower():
            title = _derive_title("html", block)
            return ExtractedArtifact(kind="html", content=block, title=title)
        elif lang in ("markdown", "md"):
            title = _derive_title("markdown", block)
            return ExtractedArtifact(kind="markdown", content=block, title=title)
        elif "<!doctype html" in block.lower() or "<html" in block.lower() or "<script" in block.lower():
            title = _derive_title("html", block)
            return ExtractedArtifact(kind="html", content=block, title=title)

    # 2. Check for raw HTML block without markdown fences
    html_match = re.search(r"(<!DOCTYPE html.*?>.*?</html>|<html.*?>.*?</html>)", model_output, re.DOTALL | re.IGNORECASE)
    if html_match:
        html_code = html_match.group(1).strip()
        title = _derive_title("html", html_code)
        return ExtractedArtifact(kind="html", content=html_code, title=title)

    # 3. If any fenced code block was found with content
    if fences:
        block = fences[0].group(2).strip()
        if block:
            is_html = "<!doctype html" in block.lower() or "<html" in block.lower()
            kind = "html" if is_html else "markdown"
            title = _derive_title(kind, block)
            return ExtractedArtifact(kind=kind, content=block, title=title)

    return None


def _derive_title(kind: str, content: str) -> Optional[str]:
    """Extract a human-readable title from the artifact content."""
    if kind == "markdown":
        # First H1 or H2 heading
        m = re.search(r"^#{1,2}\s+(.+)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()[:200]
    elif kind == "html":
        # <title> tag
        m = re.search(r"<title[^>]*>([^<]+)</title>", content, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:200]
        # <h1> tag
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", content, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:200]
    return None


# ── Main skill entry point ────────────────────────────────────────────────────

async def run(
    user_message: str,
    retrieval: RetrievalResult,
    provider: "LLMProvider",
    conversation_history: list[dict] | None = None,
) -> tuple[CompletionResponse, Optional[ExtractedArtifact]]:
    """
    Execute the artifact skill.
    Returns (CompletionResponse, ExtractedArtifact | None).
    The orchestrator saves the artifact to DB and associates it with the message.
    """
    # Detect requested kind
    user_lower = user_message.lower()
    if "html" in user_lower or "interactive" in user_lower or "dashboard" in user_lower:
        kind_hint = "HTML"
        requirements = (
            "A self-contained HTML page with inline CSS and JS if interactive. "
            "Dark theme, modern design, useful content based on the transcript context."
        )
    else:
        kind_hint = "Markdown"
        requirements = (
            "A well-structured Markdown document with headings, bullets, and bold text. "
            "Include actionable content grounded in the transcript excerpts."
        )

    context = retrieval.context_text if retrieval.is_grounded else (
        "No specific transcript context available — generate a general product/growth artifact."
    )
    system = _ARTIFACT_SYSTEM.format(context=context)

    messages: list[dict] = [{"role": "system", "content": system}]
    if conversation_history:
        messages.extend(conversation_history[-4:])  # last 2 turns for context
    messages.append({
        "role": "user",
        "content": _ARTIFACT_USER_TEMPLATE.format(
            kind=kind_hint,
            topic=user_message,
            requirements=requirements,
        ),
    })

    log.info("artifact.generating", kind=kind_hint, query=user_message[:60])
    response = await provider.complete(
        CompletionRequest(messages=messages, max_tokens=3000, temperature=0.5)
    )

    artifact = extract_artifact(response.content)

    if artifact is None:
        # Derive title from user message as fallback
        fallback_title = user_message[:60].strip()
        # Return the raw model output as a markdown artifact
        artifact = ExtractedArtifact(
            kind="markdown",
            content=response.content,
            title=fallback_title,
        )
        log.warning("artifact.fallback_to_raw", title=fallback_title)

    return response, artifact
