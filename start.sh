#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# start.sh — One-command local startup (no Docker required)
# Usage: ./start.sh [--provider ollama|anthropic|mock]
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
DATA_DIR="$REPO_DIR/data"
VENV="$BACKEND_DIR/.venv"

# ── Parse args ────────────────────────────────────────────────────────────────
PROVIDER="ollama"
while [[ $# -gt 0 ]]; do
  case $1 in
    --provider) PROVIDER="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

echo "╔═══════════════════════════════════════════╗"
echo "║    Lenny Growth Assistant — Local Start   ║"
echo "╚═══════════════════════════════════════════╝"
echo "Provider: $PROVIDER"
echo ""

# ── Check Python venv ─────────────────────────────────────────────────────────
if [[ ! -f "$VENV/bin/python" ]]; then
  echo "❌ Virtual environment not found. Run:"
  echo "   cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# ── Check Ollama (if needed) ──────────────────────────────────────────────────
if [[ "$PROVIDER" == "ollama" ]]; then
  if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠  Ollama not reachable at localhost:11434"
    echo "   Start it with: ollama serve"
    echo "   Falling back to mock provider for this run."
    PROVIDER="mock"
  else
    echo "✅ Ollama reachable ($(curl -s http://localhost:11434/api/tags | python3 -c 'import sys,json; models=json.load(sys.stdin)["models"]; print(", ".join(m["name"] for m in models))' 2>/dev/null || echo 'models found'))"
  fi
fi

# ── Kill any previous servers ─────────────────────────────────────────────────
echo ""
echo "Stopping any previous instances..."
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "http.server 3000" 2>/dev/null || true
sleep 1

# ── Start backend ─────────────────────────────────────────────────────────────
echo "Starting backend (port 8000)..."
cd "$BACKEND_DIR"
LLM_PROVIDER="$PROVIDER" \
LLM_FALLBACK_PROVIDER="mock" \
DATABASE_URL="sqlite+aiosqlite:///$DATA_DIR/lenny.db" \
BM25_INDEX_PATH="$DATA_DIR/bm25_index.pkl" \
TRANSCRIPTS_DIR="$DATA_DIR/transcripts" \
OLLAMA_BASE_URL="http://localhost:11434" \
nohup "$VENV/bin/uvicorn" app.main:app \
  --host 127.0.0.1 --port 8000 \
  > /tmp/lenny_backend.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > /tmp/lenny_backend.pid

# Wait for backend to be ready
echo -n "Waiting for backend"
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo " ✅"
    break
  fi
  echo -n "."
  sleep 1
  if [[ $i -eq 20 ]]; then
    echo " ❌ Backend failed to start. Check /tmp/lenny_backend.log"
    exit 1
  fi
done

# ── Build / verify BM25 index ─────────────────────────────────────────────────
if [[ ! -f "$DATA_DIR/bm25_index.pkl" ]]; then
  echo ""
  echo "Building BM25 index (first run — takes ~5 seconds)..."
  curl -sf -X POST http://localhost:8000/api/admin/reindex | \
    python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"  ✅ {d[\"episodes_indexed\"]} episodes, {d[\"chunks_indexed\"]} chunks ({d[\"duration_ms\"]}ms)")' \
    2>/dev/null || echo "  ⚠  Reindex failed — check transcript path"
else
  echo "✅ BM25 index already built ($(du -h "$DATA_DIR/bm25_index.pkl" | cut -f1))"
fi

# ── Start frontend ────────────────────────────────────────────────────────────
echo ""
echo "Starting frontend (port 3000)..."
cd "$FRONTEND_DIR"
nohup python3 -m http.server 3000 > /tmp/lenny_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > /tmp/lenny_frontend.pid
sleep 1

# ── Final status ──────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
HEALTH=$(curl -s http://localhost:8000/api/health 2>/dev/null || echo '{}')
echo "$HEALTH" | python3 -c "
import sys, json
try:
    h = json.load(sys.stdin)
    for name, c in h.get('components', {}).items():
        sym = '✅' if c['status'] == 'ok' else ('⚠' if c['status'] == 'degraded' else '❌')
        label = {'db':'DB','retrieval':'BM25 Index','llm_primary':'LLM Primary','llm_fallback':'LLM Fallback'}.get(name, name)
        print(f'  {sym} {label}: {c[\"status\"]}')
except: print('  Could not parse health response')
" 2>/dev/null || true
echo ""
echo "  🌐 Frontend → http://localhost:3000"
echo "  🔧 API docs  → http://localhost:8000/api/docs"
echo "══════════════════════════════════════════════"
echo ""
echo "Logs: /tmp/lenny_backend.log  /tmp/lenny_frontend.log"
echo "Stop: kill \$(cat /tmp/lenny_backend.pid) \$(cat /tmp/lenny_frontend.pid)"
echo ""
# Open browser (macOS)
if command -v open > /dev/null 2>&1; then
  open http://localhost:3000 2>/dev/null || true
fi
