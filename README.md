# Lenny Growth Assistant 🚀

A production-grade, local RAG (Retrieval-Augmented Generation) assistant trained on **303 episodes and 28,859 transcript chunks** from *Lenny's Podcast*. Built with FastAPI, SQLite (`aiosqlite`), BM25 lexical retrieval, Ollama LLM integration (with automated Mock fallback), and a modern HTML5/CSS3 frontend featuring an isolated virtual sandbox.

---

## 🏗 Architecture Overview

```
                      +-----------------------------+
                      |     Browser Frontend        |
                      |  (HTML5 / CSS / Vanilla JS) |
                      +--------------+--------------+
                                     |
                                     | REST API / HTTP
                                     v
                      +-----------------------------+
                      |     FastAPI Server Engine   |
                      |   (Uvicorn / Async Python)  |
                      +--------------+--------------+
                                     |
           +-------------------------+-------------------------+
           |                         |                         |
           v                         v                         v
+--------------------+    +--------------------+    +--------------------+
|  BM25 Index Store  |    |   Skills Engine    |    |  Security Module   |
| (rank_bm25 / pkl)  |    | (QA, Essay, Apps)  |    | (Bleach / CSP Meta)|
+---------+----------+    +----------+---------+    +--------------------+
          |                          |
          | Top-K Chunks             | Prompt Context
          v                          v
+----------------------------------------------------------------------+
|                       LLM Router & Failover                          |
|  Primary: Ollama (gemma3:4b)  ==[Failover]==> Fallback: Mock Engine  |
+----------------------------------------------------------------------+
                                     |
                                     v
                        +--------------------------+
                        |  SQLite Async Database   |
                        | (Sessions, Messages,     |
                        |     Artifact Storage)    |
                        +--------------------------+
```

---

## 🌟 Key Features

* **Sub-50ms BM25 Retrieval**: Ranked search across 28,859 podcast transcript chunks with episode metadata, guest names, and YouTube timestamp deep links.
* **Auto-Routing Skills Engine**:
  * **Q&A Skill**: Grounded answer synthesis with direct citation tags `[1]`, `[2]`, and mandatory grounding check (`NOT_GROUNDED` prefix protection).
  * **Ship30 Essay Skill**: 1,100–1,400 word action-oriented essays following the Ship 30 for 30 framework (Hook, Tension, Insight, Mechanics, and The One Thing). Self-validates structure and rewrites automatically on validation failure.
  * **Artifact Generator Skill**: Generates self-contained HTML/CSS/JS single-page web apps, tools, calculators, and interactive dashboards.
* **Virtual Sandbox Isolation**:
  * Rendered markdown sanitization against XSS (`<script>`, event handlers, `javascript:` URLs).
  * Isolated `<iframe>` sandbox for HTML artifacts using strict Content Security Policy (`default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'`) and `sandbox="allow-scripts"`.
* **Resilient Dual-Provider Architecture**:
  * Primary: Local Ollama (`gemma3:4b`).
  * Fallback: Automatic seamless fallback to structured Mock Provider if Ollama is offline or times out.
* **Session & History Persistence**: Async SQLite database (`aiosqlite` + SQLAlchemy 2.0) for multi-turn chat sessions, title auto-summarization, and artifact storage.
* **Dual Theme Engine**: Seamless Dark / Light mode toggle with persistent preferences.

---

## 📋 Prerequisites

- **Python**: Python 3.9+ (Python 3.11 recommended)
- **Local Model Provider (Optional but Recommended)**: [Ollama](https://ollama.com/) installed and running.
- **Docker (Optional)**: Docker & Docker Compose for containerized deployment.

---

## ⚙️ Environment Variables

Copy `backend/.env.example` to `backend/.env` to configure settings:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | `string` | `"Lenny Growth Assistant"` | Display name of the application |
| `DATABASE_URL` | `string` | `sqlite+aiosqlite:///./data/lenny.db` | Async database connection string |
| `LLM_PROVIDER` | `string` | `"ollama"` | Primary LLM provider (`"ollama"`, `"mock"`, `"anthropic"`) |
| `LLM_FALLBACK_PROVIDER` | `string` | `"mock"` | Fallback provider if primary is unavailable |
| `OLLAMA_BASE_URL` | `string` | `"http://localhost:11434"` | URL of the local Ollama instance |
| `OLLAMA_MODEL` | `string` | `"gemma3:4b"` | Model tag to invoke in Ollama |
| `OLLAMA_TIMEOUT` | `float` | `120.0` | Timeout in seconds for Ollama completions |
| `ANTHROPIC_API_KEY` | `string` | `""` | Optional cloud API key for Claude completions |
| `ANTHROPIC_MODEL` | `string` | `"claude-3-5-haiku-20241022"` | Anthropic model identifier |
| `TRANSCRIPTS_DIR` | `string` | `"./data/transcripts"` | Directory containing transcript JSON files |
| `BM25_INDEX_PATH` | `string` | `"./data/bm25_index.pkl"` | Path to serialized BM25 pickle cache |
| `CORS_ORIGINS` | `list` | `["*"]` | Allowed CORS origins for the API |

---

## 🧠 Model Setup (Local & Cloud)

### 1. Local Model Setup (Ollama)
```bash
# 1. Install Ollama from https://ollama.com
# 2. Pull the default Gemma model
ollama pull gemma3:4b

# 3. Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 2. Cloud Model Setup (Anthropic Claude - Optional)
Add your API key to `backend/.env`:
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
```

---

## 🚀 Run Commands

### Method 1: One-Command Native Launch (Recommended)
```bash
# Automatically configures venv, dependencies, checks Ollama, and opens the UI
./start.sh --provider ollama
```
- **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Swagger Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### Method 2: Docker Compose
```bash
cp backend/.env.example backend/.env
docker compose up --build
```

---

## 🧪 Testing

The repository includes a comprehensive 75-test automated test suite covering unit tests, API contracts, and security rules:

```bash
cd backend
.venv/bin/pytest tests/ -v
```

**Test Coverage Summary:**
- `test_phase4_skills.py`: Skill intent routing, grounding validation, Ship30 essay structure validator.
- `test_phase5_api.py`: FastAPI REST endpoints, session persistence, message history, artifact generation.
- `test_security.py`: Anti-XSS sanitization tests, iframe `srcdoc` encoding, CSP meta tag enforcement.

---

## 🛠 Troubleshooting & FAQs

### 1. `Ollama connection degraded / using fallback provider`
- **Cause**: Ollama service is not running or the model `gemma3:4b` is not pulled.
- **Solution**: Run `ollama serve` and `ollama pull gemma3:4b`. The system will automatically degrade gracefully to the `MockProvider` so you can continue using the assistant without downtime.

### 2. `Database or Index file not found`
- **Cause**: The BM25 index cache has not been generated or the path is misconfigured.
- **Solution**: Trigger a rebuild via `POST /api/admin/reindex`:
  ```bash
  curl -X POST http://localhost:8000/api/admin/reindex
  ```

### 3. `Port 8000 or 3000 already in use`
- **Cause**: A previous instance is still running in the background.
- **Solution**: Terminate existing processes:
  ```bash
  pkill -f "uvicorn app.main"
  pkill -f "http.server 3000"
  ./start.sh --provider ollama
  ```

---

## 📚 Documentation Index

- [PRD (Product Requirements Document)](file:///Users/revanth/Desktop/lenny/docs/PRD.md)
- [Design System & UI/UX](file:///Users/revanth/Desktop/lenny/docs/design.md)
- [Architecture & System Design](file:///Users/revanth/Desktop/lenny/docs/architecture.md)
- [Test Strategy & UI Test Plan](file:///Users/revanth/Desktop/lenny/docs/tests.md)
- [Agent Execution Transcripts & Build Log](file:///Users/revanth/Desktop/lenny/agent-transcripts/build_log.md)

---

## 📜 License

MIT License. Developed for the Lenny Growth Assistant.