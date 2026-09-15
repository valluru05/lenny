"""
agent/providers/mock_provider.py — Deterministic stub for tests and demo fallback.

Returns realistic-looking structured responses without any network calls.
Skill-aware: returns different mock content depending on the system prompt keywords.
Used as:
  - LLM_PROVIDER=mock  → zero-dependency local dev / CI
  - Fallback of last resort if both primary and fallback providers fail
"""
from __future__ import annotations

from app.agent.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
)
from app.logging_conf import get_logger

log = get_logger("provider.mock")

_QA_RESPONSE = """Based on the provided transcript excerpts, here is a grounded answer to your question.

The key insight from the sources is that successful product teams focus relentlessly on outcomes rather than outputs. As discussed in the transcript, the most effective approach involves:

**Understanding the problem deeply before jumping to solutions.** The guests consistently emphasize spending time in discovery to validate assumptions before committing engineering resources.

**Measuring what matters.** Rather than tracking vanity metrics, world-class growth teams instrument the specific behaviors that predict long-term retention and revenue.

**Iterating quickly with small bets.** The evidence from multiple episodes points to a cadence of rapid experiments over big-bang releases.

*[Mock response — configure LLM_PROVIDER=anthropic or LLM_PROVIDER=ollama for real answers]*"""

_ESSAY_RESPONSE = """## The One Growth Insight Every PM Ignores (Until It's Too Late)

Most product managers obsess over acquisition. They track installs, signups, traffic. They celebrate when the numbers go up.

But the PMs who build lasting products? They obsess over something else entirely.

**They obsess over the moment a user first succeeds.**

### Why Activation Beats Acquisition Every Time

Here's the uncomfortable truth: getting users in the door means nothing if they walk straight out the back.

The data is unambiguous. Products with strong activation rates — where users experience genuine value within the first session — compound their growth in ways that pure acquisition never can.

You're not building an audience. You're building a habit.

### The Three Levers Most Teams Miss

**1. Define your "aha moment" with precision.** Not "user completes onboarding" — that's an output. The aha moment is the first time a user accomplishes something they couldn't before. Map it. Measure it. Ruthlessly remove everything that stands between a new user and that moment.

**2. Remove steps, don't add features.** Every additional screen, form field, or decision point is a toll gate. The instinct to add more guidance is almost always wrong. The insight is counterintuitive: the shorter the path, the more users find their way.

**3. Make the first success visible.** Users need to feel the product working. Progress indicators, early wins, immediate feedback — these aren't UX polish, they're retention infrastructure.

### The Takeaway

Your acquisition funnel is a leaky bucket. No amount of new users fixes a product that doesn't deliver on its promise fast enough.

Pick one user action that represents genuine value delivered. Measure how many new users reach it within 24 hours. Then make that number your north star — not installs, not pageviews, not MAU.

The products that win long-term are the ones that earn the second session.

*[Mock essay — configure LLM_PROVIDER=anthropic or LLM_PROVIDER=ollama for real generation]*"""

_ARTIFACT_MARKDOWN = """```markdown
# Growth Strategy Playbook

## Core Principles

- **Outcome over output**: measure user value, not feature count
- **Activation before acquisition**: fix the leaky bucket first  
- **Small bets, fast learning**: weekly experiments over quarterly releases

## Key Frameworks

### The AARRR Funnel
1. **Acquisition** — How do users find you?
2. **Activation** — Do users have a great first experience?
3. **Retention** — Do users come back?
4. **Revenue** — How do you monetize?
5. **Referral** — Do users tell others?

### North Star Metric
Your NSM should be a single number that best captures the value your product delivers to customers.

*Source: Lenny's Podcast transcripts*
```"""

_ARTIFACT_HTML = """```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Growth Dashboard</title>
<style>
  body { font-family: system-ui, sans-serif; padding: 2rem; background: #0f172a; color: #e2e8f0; }
  .metric { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin: 1rem 0; }
  .value { font-size: 2.5rem; font-weight: 700; color: #38bdf8; }
  .label { font-size: 0.875rem; color: #94a3b8; margin-top: 0.25rem; }
</style>
</head>
<body>
  <h1>📈 Growth Metrics</h1>
  <div class="metric"><div class="value">68%</div><div class="label">7-day retention</div></div>
  <div class="metric"><div class="value">42%</div><div class="label">Activation rate (24h)</div></div>
  <div class="metric"><div class="value">3.2x</div><div class="label">Viral coefficient</div></div>
</body>
</html>
```"""


class MockProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return "mock-v1"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        log.debug("mock.complete", messages=len(request.messages))

        # Detect skill from system prompt keywords
        system_text = " ".join(
            m["content"] for m in request.messages if m.get("role") == "system"
        ).lower()

        user_text = " ".join(
            m["content"] for m in request.messages if m.get("role") == "user"
        ).lower()

        if "ship 30" in system_text or "essay" in system_text:
            content = _ESSAY_RESPONSE
        elif "artifact" in system_text or "html" in user_text or "markdown" in user_text:
            if "html" in user_text:
                content = _ARTIFACT_HTML
            else:
                content = _ARTIFACT_MARKDOWN
        else:
            content = _QA_RESPONSE

        return CompletionResponse(
            content=content,
            provider="mock",
            model="mock-v1",
            input_tokens=len(" ".join(m["content"] for m in request.messages).split()),
            output_tokens=len(content.split()),
        )

    async def health_check(self) -> bool:
        return True
