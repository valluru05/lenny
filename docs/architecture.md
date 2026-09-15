# Architecture & System Design — Lenny Growth Assistant

This document provides the definitive architectural specification for the Lenny Growth Assistant, covering database schema, API surface, component boundaries, retrieval flow, skill routing, security sandboxing, and deployment topology.

---

## 1. System Topology & Component Diagram

```
                              +---------------------------------------+
                              |         Browser Client (SPA)          |
                              |  HTML5 / Modern CSS / Vanilla JS      |
                              +-------------------+-------------------+
                                                  |
                                                  | HTTP / JSON REST
                                                  v
                              +---------------------------------------+
                              |      Nginx Reverse Proxy / Port 80    |
                              +-------------------+-------------------+
                                                  |
                                                  | Proxied to :8000
                                                  v
                      +-------------------------------------------------------+
                      |               FastAPI Server Engine                   |
                      |            (Uvicorn / Async Python 3.11)              |
                      +---------------------------+---------------------------+
                                                  |
                     +----------------------------+----------------------------+
                     |                            |                            |
                     v                            v                            v
       +----------------------------+  +----------------------+  +----------------------------+
       |     BM25 Search Service    |  |     Skills Engine    |  |   Security & Sandbox Core  |
       |  (rank_bm25 / 28.8k Chunks)|  | (QA, Essay, Artifact)|  | (Bleach Anti-XSS, CSP Meta)|
       +--------------+-------------+  +----------+-----------+  +----------------------------+
                      |                           |
                      | Top-K Chunks Context      | System & Prompt Assembly
                      +---------------------+-----+
                                            |
                                            v
                      +-----------------------------------------------+
                      |           LLM Router & Failover Engine        |
                      |                                               |
                      |  Primary: Ollama (gemma3:4b)                  |
                      |    │ (On Connection Error / Timeout / 503)    |
                      |    ▼                                          |
                      |  Fallback: Deterministic Mock Provider        |
                      |  Optional Cloud: Anthropic Claude 3.5 Haiku   |
                      +---------------------+-------------------------+
                                            |
                                            v
                      +-----------------------------------------------+
                      |            Async Persistence Layer            |
                      |         SQLAlchemy 2.0 + SQLite (aiosqlite)   |
                      |         (sessions, messages, artifacts)       |
                      +-----------------------------------------------+
```

---

## 2. Database Schema

The persistence layer uses asynchronous SQLite via `aiosqlite` and `SQLAlchemy 2.0`. All tables enforce UUID primary keys and cascading foreign key relationships.

```
+--------------------+          +--------------------+          +--------------------+
|    chat_sessions   | 1      * |   chat_messages    | 1      1 |     artifacts      |
+--------------------+          +--------------------+          +--------------------+
| id (UUID, PK)      |<---------| session_id (FK)    |          | id (UUID, PK)      |
| title (VARCHAR)    |          | id (UUID, PK)      |<---------| message_id (FK)    |
| created_at (DATETIME)         | role (VARCHAR)     |          | kind (VARCHAR)     |
| updated_at (DATETIME)         | content (TEXT)     |          | title (VARCHAR)    |
+--------------------+          | skill (VARCHAR)    |          | content (TEXT)     |
                                | provider (VARCHAR) |          | sanitized (BOOL)   |
                                | model (VARCHAR)    |          | created_at (DATETIME)
                                | used_fallback(BOOL)|          +--------------------+
                                | is_grounded (BOOL) |
                                | sources_json(TEXT) |
                                | latency_ms (INT)   |
                                | created_at(DATETIME|
                                +--------------------+
```

### Table Definitions
1. **`chat_sessions`**:
   - `id`: `String(36)`, Primary Key (UUIDv4).
   - `title`: `String(255)`, defaults to `"New Chat"`, updated automatically from the first user prompt.
   - `created_at` / `updated_at`: `DateTime(timezone=True)`.
2. **`chat_messages`**:
   - `id`: `String(36)`, Primary Key (UUIDv4).
   - `session_id`: `String(36)`, Foreign Key referencing `chat_sessions.id` (ON DELETE CASCADE).
   - `role`: `"user"` | `"assistant"`.
   - `content`: `Text`, raw prompt or rendered markdown completion.
   - `skill`: `"qa"` | `"ship30_essay"` | `"artifact"`.
   - `provider`: `"ollama"` | `"mock"` | `"anthropic"`.
   - `model`: Model version tag (e.g. `gemma3:4b`).
   - `used_fallback`: Boolean indicating if failover occurred.
   - `is_grounded`: Boolean indicating if response met grounding threshold.
   - `sources_json`: Serialized JSON array of retrieved chunks.
   - `latency_ms`: Total execution time in milliseconds.
3. **`artifacts`**:
   - `id`: `String(36)`, Primary Key (UUIDv4).
   - `message_id`: `String(36)`, Foreign Key referencing `chat_messages.id` (ON DELETE CASCADE).
   - `kind`: `"html"` | `"markdown"`.
   - `title`: String extracted from heading or `<title>` tag.
   - `content`: Raw HTML/CSS/JS source or markdown text.
   - `sanitized`: Boolean tracking render-time security processing.

---

## 3. Ingestion & Retrieval Pipeline (RAG)

```
[ 303 Podcast Transcripts ]
            │
            ▼
[ Chunker (`app/rag/chunker.py`) ]
  • Frontmatter metadata extraction (Episode #, Title, Guest Name, YouTube URL)
  • Sliding window tokenization: 200 words/chunk, 40 words overlap
  • Total Chunks: 28,859 structured documents
            │
            ▼
[ Index Store (`app/rag/index_store.py`) ]
  • Okapi BM25 Index (`rank_bm25`)
  • Persisted as serialized binary cache: `data/bm25_index.pkl` (66.9 MB)
  • Zero external vector database dependencies (sub-50ms query time)
            │
            ▼
[ Retriever (`app/rag/retriever.py`) ]
  • Top-K: Returns top 8 relevant chunks
  • Score Calibration: Threshold = 15.5
  • Returns `RetrievalResult(is_grounded, sources, context_text)`
```

---

## 4. Agent Routing & Skills Engine

The orchestrator classifies intent and manages domain-specific execution pipelines:

```
[ User Message ] 
       │
       ├── Matches Artifact Keywords / "generate html / dashboard / calculator" ──> [ Artifact Skill ]
       │                                                                                  │
       ├── Matches Essay Keywords / "write essay / ship 30 / blog" ───────────────> [ Ship30 Essay Skill ]
       │                                                                                  │
       └── Default Conversational Query ──────────────────────────────────────────> [ Q&A Skill ]
```

### 4.1 Q&A Skill (`app/agent/skills/qa_skill.py`)
- Injects top transcript excerpts into prompt with explicit guest attribution rules.
- Grounding check validates that response claims correlate with transcript source chunks.
- Ungrounded responses are prepended with `<!-- NOT_GROUNDED -->` guard.

### 4.2 Ship 30 for 30 Essay Skill (`app/agent/skills/ship30_skill.py`)
- **Structure Contract**: Hook (1–3 lines) → Tension → Insight → Mechanics → "## The One Thing" takeaway.
- **Length Constraint**: Strictly 1,100–1,400 words with ≥ 3 section headings and bold key phrases.
- **Agentic Self-Check Loop**: Automatically validates generated text. If structural contract fails, an automated revision pass is executed before returning.
- **Virtual Sandbox Binding**: Automatically packaged as a markdown artifact for right-panel sandbox viewing.

### 4.3 Artifact Generator Skill (`app/agent/skills/artifact_skill.py`)
- Generates self-contained, single-page HTML/CSS/JS tools, calculators, and dashboards.
- Extracts code blocks using regex pattern matchers supporting both explicit fences and raw markup.

---

## 5. Model Toggle & Resilient Failover Topology

```
[ Request Execution ]
         │
         ▼
[ Primary Provider: Ollama (`gemma3:4b`) ] ──(Success)──> [ Return Response ]
         │
         ├── Connection Refused
         ├── Timeout (> 120s)
         └── HTTP Error
         │
         ▼
[ Fallback Provider: Mock Engine (`mock-v1`) ] ──(Success)──> [ Return Grounded Response + Fallback Banner ]
```

- **Seamless Recovery**: If Ollama goes offline or the host machine is overloaded, the assistant falls back to the deterministic `MockProvider` without surfacing 500 error alerts to the user.
- **Runtime Provider Override**: Users can dynamically switch providers per-message or test alternative completions using the "Regenerate" button.

---

## 6. Security Architecture & Sandboxing

### 6.1 Markdown Anti-XSS Sanitization (`app/security/sanitize.py`)
- Sanitizes rendered markdown before passing to the browser.
- Strips `<script>`, `<object>`, `<embed>`, `<iframe>`, `onclick`, `onload`, `onerror`, and `javascript:` URIs using `bleach`.

### 6.2 Virtual Sandbox Iframe Isolation (`app/security/sandbox.py`)
- Generated HTML applications run inside an isolated `<iframe>` element.
- **Sandbox Attribute**: `sandbox="allow-scripts"` (strictly forbids `allow-same-origin`, `allow-forms`, and `allow-popups`).
- **Content Security Policy (CSP)**: Injects `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: https:; connect-src 'none';">`.
- Blocks all outbound network requests (`fetch`, `XMLHttpRequest`, `WebSocket`), prevents access to `document.cookie`, and prevents parent DOM traversal.

---

## 7. REST API Endpoints Specification

| Method | Endpoint | Description | Request Body | Response Status |
|--------|----------|-------------|--------------|-----------------|
| `GET` | `/api/health` | System health check (DB, BM25, Ollama, Fallback) | None | `200 OK` |
| `GET` | `/api/sessions` | List all chat sessions | None | `200 OK` |
| `POST` | `/api/sessions` | Create a new session | `{"title": "New Chat"}` | `201 Created` |
| `GET` | `/api/sessions/{id}` | Retrieve session details & full message history | None | `200 OK` |
| `PATCH` | `/api/sessions/{id}` | Update session title | `{"title": "Updated Title"}` | `200 OK` |
| `DELETE`| `/api/sessions/{id}` | Delete session and associated messages/artifacts | None | `204 No Content` |
| `POST` | `/api/sessions/{id}/chat`| Main generation endpoint | `{"message": str, "skill": str}` | `200 OK` |
| `GET` | `/api/artifacts/{id}` | Retrieve sandboxed artifact by ID | None | `200 OK` |
| `POST` | `/api/admin/reindex` | Force rebuild of BM25 pickle cache | None | `200 OK` |

---

## 8. Deployment Topology

```
+─────────────────────────────────────────────────────────────────────────────+
|                             Docker Compose Stack                            |
|                                                                             |
|  +──────────────────────────────────+   +────────────────────────────────+  |
|  |       Frontend (Nginx)           |   |       Backend (FastAPI)        |  |
|  |  • Port 80 (HTTP)                |──>|  • Port 8000 (Internal)        |  |
|  |  • Serves static SPA files       |   |  • Multi-stage Python 3.11     |  |
|  |  • Proxies /api/* to backend     |   |  • Bind mounts /data           |  |
|  +──────────────────────────────────+   +────────────────────────────────+  |
|                                                                             |
|  +───────────────────────────────────────────────────────────────────────+  |
|  | Host Machine: Ollama Service (http://host.docker.internal:11434)       |  |
|  +───────────────────────────────────────────────────────────────────────+  |
+─────────────────────────────────────────────────────────────────────────────+
```
