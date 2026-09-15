# Agent Build Log & Execution Transcripts
## Project: Lenny Growth Assistant

This document contains the chronological record of the development phases, technical challenges encountered, failure modes identified, and the specific self-corrections applied throughout the build process. All API keys and sensitive environment values have been scrubbed.

---

## 1. Phase-by-Phase Development Log

### Phase 0 — Data Acquisition & Schema Normalization
- **Objective**: Ingest transcript data from `ChatPRD/lennys-podcast-transcripts`.
- **Outcome**: Successfully imported 303 episode files across Markdown/JSON formats.
- **Normalization**: Normalized episode frontmatter (`episode_number`, `title`, `guest`, `youtube_url`).

### Phase 1 — Core Backend Architecture
- **Objective**: Set up FastAPI, async database engine (`aiosqlite` + SQLAlchemy 2.0), logging, and settings configuration.
- **Components**: `config.py`, `db.py`, `models.py`, `schemas.py`, `deps.py`, `main.py`.

### Phase 2 — Lexical RAG & Chunking Pipeline
- **Objective**: Split episodes into 200-word sliding windows with 40-word overlap; build Okapi BM25 index.
- **Outcome**: Generated 28,859 searchable chunks; persisted index as `data/bm25_index.pkl` (66.9 MB). Sub-50ms lexical retrieval verified across known queries.

### Phase 3 — LLM Provider Layer & Failover Router
- **Objective**: Implement `LLMProvider` abstraction, local Ollama client (`gemma3:4b`), deterministic Mock provider, and failover router.

### Phase 4 — Auto-Routing Skills Engine
- **Objective**: Implement Q&A Grounding skill, Ship30 essay skill with agentic self-check revision loop, and HTML/Markdown artifact generator skill.

### Phase 5 — API Surface
- **Objective**: Build REST endpoints for sessions, chat, artifacts, health, and reindexing.

### Phase 6 — Enterprise Security & Sandboxing
- **Objective**: Implement Bleach-based anti-XSS markdown sanitizer and iframe sandbox CSP generator.

### Phase 7 — Responsive Frontend SPA
- **Objective**: Build clean dark/light theme single page interface with vanilla HTML/CSS/JS, collapsible source drawers, and right-side virtual sandbox drawer.

### Phase 8 — Docker Compose & One-Command Startup
- **Objective**: Create multi-stage `Dockerfile`, `docker-compose.yml`, `nginx.conf`, and `start.sh` runner script.

### Phase 9 — Test Suite & Quality Assurance
- **Objective**: Build comprehensive test suite covering all units, API endpoints, and security properties (75/75 passing).

---

## 2. Issues Encountered & Self-Corrections

### Challenge 1: Docker Database Path vs. Native Path Collision
- **Symptom**: Running `./start.sh` natively produced `OperationalError: unable to open database file` because `.env` specified Docker container path `sqlite+aiosqlite:////app/data/lenny.db`.
- **Root Cause**: The `.env` file was templated for Docker container directories (`/app/data`), which do not exist on the host filesystem during native execution.
- **Correction Applied**: Updated `start.sh` to explicitly pass local path overrides (`DATABASE_URL="sqlite+aiosqlite:///$DATA_DIR/lenny.db"`, `OLLAMA_BASE_URL="http://localhost:11434"`) and updated `config.py` with multi-path resolution defaults.

### Challenge 2: Client-Side `Error: api is not defined` Alert
- **Symptom**: Clicking "+ New Chat" or loading sessions in the browser triggered a JavaScript alert popup saying `Error: api is not defined`.
- **Root Cause**: During a frontend file update, the `async function api(method, path, body)` helper function was inadvertently omitted from `app.js`.
- **Correction Applied**: Restored the async `api()` wrapper in `frontend/app.js` with proper JSON parsing and HTTP status code validation.

### Challenge 3: Cross-Origin Iframe Inspection Error in Browser Subagent
- **Symptom**: Browser console logged `SecurityError: Blocked a frame with origin "http://localhost:3000" from accessing a cross-origin frame`.
- **Root Cause**: Because the sandbox iframe strictly omits `allow-same-origin` (a security requirement), automated DOM inspection tools attempt to read `iframe.contentDocument` across the boundary.
- **Correction Applied**: Added an `error` listener in `app.js` to catch cross-origin security errors gracefully while maintaining total security isolation.

### Challenge 4: Missing Artifact Extraction on Unformatted LLM Output
- **Symptom**: Asking for an HTML calculator rendered raw code in the chat bubble instead of opening the right-side virtual sandbox.
- **Root Cause**: The regex in `artifact_skill.py` strictly looked for ` ```html ` fences. When local models outputted generic ` ``` ` blocks or raw `<!DOCTYPE html>`, extraction returned `None`.
- **Correction Applied**: Enhanced `extract_artifact()` in `artifact_skill.py` to recognize raw `<!DOCTYPE html>`, `<html>`, generic fences, and markdown headings, and added auto-extraction in `orchestrator.py` across all skill paths.

### Challenge 5: Pydantic Validation on Empty Environment Variables
- **Symptom**: `Settings` initialization crashed if `.env` had `LLM_FALLBACK_PROVIDER=""` or `ANTHROPIC_API_KEY=""`.
- **Root Cause**: Pydantic's `Literal` type rejected empty strings.
- **Correction Applied**: Added `@field_validator("anthropic_api_key", "llm_fallback_provider", mode="before")` in `config.py` converting empty or whitespace strings into `None`.

---

## 3. Scrubbed Environment Confirmation

All sensitive API keys and tokens have been scrubbed from this repository and transcripts:
- `ANTHROPIC_API_KEY`: Scrubbed / empty by default.
- Local endpoints strictly target `localhost` and `host.docker.internal`.
