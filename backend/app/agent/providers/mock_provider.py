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
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Retention & Growth Dashboard</title>
<style>
  :root {
    --bg-dark: #080c14;
    --card-bg: #111827;
    --card-border: rgba(56, 189, 248, 0.15);
    --accent-blue: #38bdf8;
    --accent-green: #10b981;
    --accent-amber: #f59e0b;
    --accent-purple: #a855f7;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg-dark);
    color: var(--text-main);
    padding: 24px;
    min-height: 100vh;
  }
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--card-border);
  }
  .title-group h1 { font-size: 22px; font-weight: 800; color: #fff; letter-spacing: -0.02em; }
  .title-group p { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
  .live-badge {
    background: rgba(16, 185, 129, 0.15);
    color: var(--accent-green);
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
  
  /* KPI Grid */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }
  .kpi-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 18px;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s ease, border-color 0.2s ease;
  }
  .kpi-card:hover { transform: translateY(-2px); border-color: var(--accent-blue); }
  .kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
  }
  .kpi-label { font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.05em; }
  .kpi-value { font-size: 26px; font-weight: 800; color: #fff; margin: 8px 0 4px; letter-spacing: -0.02em; }
  .kpi-sub { font-size: 12px; color: var(--accent-green); display: flex; align-items: center; gap: 4px; font-weight: 600; }
  
  /* Layout columns */
  .grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 24px;
  }
  @media (max-width: 768px) { .grid-2col { grid-template-columns: 1fr; } }
  
  .panel {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 20px;
  }
  .panel-title { font-size: 15px; font-weight: 700; margin-bottom: 16px; color: var(--text-main); display: flex; justify-content: space-between; align-items: center; }
  
  /* Calculator inputs */
  .calc-group { margin-bottom: 14px; }
  .calc-label { display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
  .calc-label span:last-child { color: var(--accent-blue); font-family: monospace; }
  input[type="range"] {
    width: 100%;
    accent-color: var(--accent-blue);
    background: #1f2937;
    border-radius: 8px;
    height: 6px;
    outline: none;
    cursor: pointer;
  }
  
  /* Funnel bars */
  .funnel-step { margin-bottom: 12px; }
  .funnel-header { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }
  .funnel-bar-bg { background: rgba(255, 255, 255, 0.05); border-radius: 6px; height: 10px; overflow: hidden; }
  .funnel-bar-fill { height: 100%; border-radius: 6px; transition: width 0.4s ease; }
  
  /* Retention Chart Visual */
  .chart-container {
    height: 140px;
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding-top: 20px;
  }
  .chart-bar-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    justify-content: flex-end;
  }
  .chart-bar {
    width: 100%;
    background: linear-gradient(180deg, var(--accent-blue), rgba(56, 189, 248, 0.2));
    border-radius: 4px 4px 0 0;
    transition: height 0.4s ease;
    min-height: 6px;
  }
  .chart-label { font-size: 10px; color: var(--text-muted); margin-top: 6px; font-family: monospace; }
</style>
</head>
<body>
  <div class="header">
    <div class="title-group">
      <h1>📊 Retention & Growth Model</h1>
      <p>Data Model: Lenny Growth Knowledge Base • Interactive Live Simulator</p>
    </div>
    <div class="live-badge">
      <div class="live-dot"></div>
      SANDBOX LIVE
    </div>
  </div>

  <!-- KPI Overview -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Projected ARR</div>
      <div class="kpi-value" id="kpi-arr">$2.45M</div>
      <div class="kpi-sub">▲ +18.4% YoY</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Day 30 Retention</div>
      <div class="kpi-value" id="kpi-retention" style="color: var(--accent-blue);">48.5%</div>
      <div class="kpi-sub">Top 10% SaaS Benchmark</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Monthly Churn</div>
      <div class="kpi-value" id="kpi-churn" style="color: var(--accent-amber);">2.8%</div>
      <div class="kpi-sub">▼ -0.5% vs Last Mo</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Customer LTV</div>
      <div class="kpi-value" id="kpi-ltv" style="color: var(--accent-green);">$4,280</div>
      <div class="kpi-sub">LTV:CAC Ratio 4.2x</div>
    </div>
  </div>

  <div class="grid-2col">
    <!-- Simulator Panel -->
    <div class="panel">
      <div class="panel-title">
        <span>⚙️ Live Growth Simulator</span>
        <span style="font-size: 11px; color: var(--accent-blue); font-weight: 500;">Real-time Dynamic</span>
      </div>
      <div class="calc-group">
        <div class="calc-label"><span>Monthly New Signups</span><span id="lbl-signups">5,000</span></div>
        <input type="range" id="rng-signups" min="1000" max="25000" step="500" value="5000">
      </div>
      <div class="calc-group">
        <div class="calc-label"><span>Activation Rate (24h)</span><span id="lbl-activation">42%</span></div>
        <input type="range" id="rng-activation" min="10" max="80" step="1" value="42">
      </div>
      <div class="calc-group">
        <div class="calc-label"><span>Average Order / ACV</span><span id="lbl-arpu">$65 /mo</span></div>
        <input type="range" id="rng-arpu" min="10" max="250" step="5" value="65">
      </div>
      <div class="calc-group">
        <div class="calc-label"><span>Monthly Churn Rate</span><span id="lbl-churn">2.8%</span></div>
        <input type="range" id="rng-churn" min="0.5" max="10.0" step="0.1" value="2.8">
      </div>
    </div>

    <!-- Cohort Retention Curve -->
    <div class="panel">
      <div class="panel-title">
        <span>📈 Cohort Retention Curve (D1 - D90)</span>
      </div>
      <div class="chart-container" id="chart-bars">
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 100%;"></div><div class="chart-label">D1</div></div>
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 72%;"></div><div class="chart-label">D7</div></div>
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 58%;"></div><div class="chart-label">D14</div></div>
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 48%;"></div><div class="chart-label">D30</div></div>
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 44%;"></div><div class="chart-label">D60</div></div>
        <div class="chart-bar-wrap"><div class="chart-bar" style="height: 42%;"></div><div class="chart-label">D90</div></div>
      </div>
      
      <div style="margin-top: 18px;">
        <div class="funnel-step">
          <div class="funnel-header"><span style="color:var(--text-muted)">Visitors → Signups</span><span id="funnel-v2s">12.4%</span></div>
          <div class="funnel-bar-bg"><div class="funnel-bar-fill" style="width: 85%; background: var(--accent-blue);"></div></div>
        </div>
        <div class="funnel-step">
          <div class="funnel-header"><span style="color:var(--text-muted)">Signups → Activated Users</span><span id="funnel-s2a">42.0%</span></div>
          <div class="funnel-bar-bg"><div class="funnel-bar-fill" id="bar-activation" style="width: 42%; background: var(--accent-purple);"></div></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function updateCalc() {
      const signups = parseInt(document.getElementById('rng-signups').value);
      const activation = parseInt(document.getElementById('rng-activation').value);
      const arpu = parseInt(document.getElementById('rng-arpu').value);
      const churn = parseFloat(document.getElementById('rng-churn').value);

      document.getElementById('lbl-signups').textContent = signups.toLocaleString();
      document.getElementById('lbl-activation').textContent = activation + '%';
      document.getElementById('lbl-arpu').textContent = '$' + arpu + ' /mo';
      document.getElementById('lbl-churn').textContent = churn.toFixed(1) + '%';

      const activeUsers = Math.round(signups * (activation / 100));
      const mrr = Math.round(activeUsers * arpu * (1 - churn/100));
      const arr = (mrr * 12) / 1000000;
      const ltv = Math.round((arpu * (1 / (churn / 100))));
      const d30Ret = Math.max(10, Math.round(activation * 1.15 - churn * 2));

      document.getElementById('kpi-arr').textContent = '$' + arr.toFixed(2) + 'M';
      document.getElementById('kpi-retention').textContent = d30Ret + '%';
      document.getElementById('kpi-churn').textContent = churn.toFixed(1) + '%';
      document.getElementById('kpi-ltv').textContent = '$' + ltv.toLocaleString();

      document.getElementById('bar-activation').style.width = activation + '%';
      document.getElementById('funnel-s2a').textContent = activation.toFixed(1) + '%';
    }

    document.querySelectorAll('input[type="range"]').forEach(input => {
      input.addEventListener('input', updateCalc);
    });
    updateCalc();
  </script>
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
