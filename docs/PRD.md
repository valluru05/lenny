# Product Requirements Document (PRD)
## Project: Lenny Growth Assistant

---

## 1. Overview & Problem Statement

### 1.1 The Problem
Lenny's Podcast has published over 300 in-depth conversations with world-class product leaders, growth practitioners, and founders. While this archive represents one of the highest-density knowledge repositories on product-led growth, retention, hiring, and company building, finding specific tactical advice, comparing frameworks, or converting insights into actionable deliverables (e.g. structured essays or calculators) is time-consuming and inefficient via standard audio search.

### 1.2 The Solution
**Lenny Growth Assistant** is an intelligent, local RAG-powered assistant grounded exclusively in 303 podcast transcripts (28,859 chunks). It provides:
1. Grounded conversational Q&A with direct transcript citations and YouTube timestamp links.
2. Structured long-form essay generation following the Ship 30 for 30 framework with automated self-checking.
3. Live single-page HTML application generation (growth calculators, retention cohorts, dashboards) rendered in a secure virtual sandbox.
4. Resilient multi-provider LLM orchestration supporting local models (Ollama/gemma3:4b) and automated mock fallback.

---

## 2. Target Users & Personas

- **Product Managers (PMs / GPMs / VPs)**: Looking for battle-tested product management frameworks (onboarding, feature prioritization, PMF signals).
- **Growth Practitioners & Marketers**: Searching for growth loops, viral mechanics, retention strategies, and CAC:LTV optimization.
- **Founders & Early-Stage Operators**: Seeking actionable hiring, culture, pricing, and 0-to-1 playbook advice.

---

## 3. Success Metrics (KPIs)

| Metric | Target | Measurement Method |
|--------|--------|---------------------|
| **Retrieval Latency** | `< 50ms` | BM25 retrieval benchmark over 28,859 chunks |
| **Grounding Precision** | `> 90%` | Verifiable quote verification against transcript context |
| **Hallucination Protection** | `100%` | Auto-tag ungrounded claims with `NOT_GROUNDED` guard |
| **Provider Fault Tolerance** | `100% uptime` | Seamless failover to fallback provider on primary timeout |
| **UI Responsiveness** | `< 100ms` | Client-side DOM render time with zero build step |
| **Automated Test Coverage** | `100% pass rate` | 75/75 Pytest integration & security unit tests |

---

## 4. Key Assumptions & Constraints

- **Local Execution**: Must run locally without requiring expensive cloud GPU infrastructure.
- **Zero Hallucination Tolerance**: Must never invent quotes or misattribute insights to guests.
- **Isolated Execution**: User-generated or LLM-generated HTML code must run in an isolated sandbox with zero access to cookies, parent DOM, or external networks.

---

## 5. Scope & Feature Matrix

### 5.1 In-Scope (P0 / P1)
- **P0**: BM25 Indexing of 303 podcast episodes with frontmatter and timestamp metadata.
- **P0**: Grounded Q&A skill with citations (`[1]`, `[2]`), guest attribution, and YouTube deep links.
- **P0**: Ship 30 for 30 essay skill with automated validation loop.
- **P0**: Virtual Sandbox panel for HTML application rendering and markdown document preview.
- **P0**: Dual LLM provider support (Ollama primary + Mock fallback).
- **P1**: Dark/Light theme toggle with persistent preferences.
- **P1**: Multi-turn session management with SQLite persistence.
- **P1**: Anti-XSS sanitization and Content Security Policy (CSP) enforcement.

### 5.2 Out-of-Scope (Future Enhancements)
- Multi-user authentication & cloud sync (local-first for v1.0).
- Audio waveform playback inside the UI.

---

## 6. User Flows & Interaction Lifecycle

```
[ User Input / Query ]
          │
          ▼
[ Skill Intent Classifier ] ──> Auto-route (Q&A / Essay / Interactive Artifact)
          │
          ▼
[ BM25 Lexical Retrieval ] ──> Fetch Top-8 Chunks from 28,859 indexed chunks
          │
          ▼
[ LLM Router & Generation ] ──> Ollama (gemma3:4b) ─[Failover]─> Mock Engine
          │
          ▼
[ Self-Correction / Validation ] ──> Ship30 Quality Contract Check
          │
          ▼
[ Response Persistence & UI Dispatch ]
          ├── Chat Bubble (Formatted Markdown + Source Drawer)
          └── Virtual Sandbox Panel (Live HTML App / Formatted Essay)
```

---

## 7. Acceptance Criteria

1. **Grounded Retrieval**:
   - Every response citing podcast guests must include collapsible source drawer with episode number, guest name, BM25 score, and YouTube timestamp link.
2. **Essay Quality Contract**:
   - Ship30 essays must contain an immediate bold hook, ≥3 section headings, skimmable bullet points, and conclude with `## The One Thing`.
3. **Artifact Sandbox Isolation**:
   - Generated HTML code must render inside an `<iframe>` with `sandbox="allow-scripts"` and strict CSP (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'`).
4. **Resilience**:
   - If Ollama is killed or times out, the system must seamlessly fall back to `MockProvider` and display a warning banner without throwing a 500 error.
5. **Theme Support**:
   - Both Dark and Light themes must be fully supported with smooth transitions and stored preference in `localStorage`.

---

## 8. Risks & Mitigation Strategies

| Risk | Impact | Mitigation Strategy |
|------|--------|---------------------|
| Local Ollama LLM latency on low-end hardware | Medium | Configurable timeout guards and automatic failover to mock provider |
| Malicious script injection in generated HTML | High | Strict iframe sandboxing without `allow-same-origin` and CSP meta headers |
| BM25 memory footprint | Low | Serialized pickle cache with sub-50ms query latency |
