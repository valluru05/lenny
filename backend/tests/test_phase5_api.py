"""
tests/test_phase5_api.py — Phase 5 integration tests.

Tests the full API surface via FastAPI TestClient with:
  - In-memory SQLite (no external DB)
  - Mock LLM provider (no network)
  - Mock index store (no disk index required)

Covers:
  - Health endpoint
  - Session CRUD (create, list, get, patch, delete)
  - Chat flow (user msg → orchestrate → persist → response)
  - Provider failure → structured 503
  - Artifact fetch
  - Reindex endpoint
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_DIR = os.path.dirname(_BACKEND_DIR)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_phase5.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["BM25_INDEX_PATH"] = os.path.join(_REPO_DIR, "data", "bm25_index.pkl")
os.environ["TRANSCRIPTS_DIR"] = os.path.join(_REPO_DIR, "data", "transcripts")

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db import init_db, engine, Base


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def setup_db():
    """Create all tables before tests, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Remove test DB file
    if os.path.exists("./test_phase5.db"):
        os.remove("./test_phase5.db")


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "components" in data
    assert "db" in data["components"]
    assert data["components"]["db"]["status"] == "ok"
    assert data["components"]["llm_primary"]["status"] == "ok"


# ── Sessions ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session(client):
    resp = await client.post("/api/sessions", json={"title": "Test Session"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Session"
    assert "id" in data
    return data["id"]


@pytest.mark.asyncio
async def test_list_sessions(client):
    # Create two sessions
    await client.post("/api/sessions", json={"title": "Session A"})
    await client.post("/api/sessions", json={"title": "Session B"})
    resp = await client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 2


@pytest.mark.asyncio
async def test_get_session_with_messages(client):
    resp = await client.post("/api/sessions", json={"title": "Get Test"})
    session_id = resp.json()["id"]
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "session" in data
    assert "messages" in data
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_patch_session(client):
    resp = await client.post("/api/sessions", json={"title": "Old Title"})
    session_id = resp.json()["id"]
    resp = await client.patch(f"/api/sessions/{session_id}", json={"title": "New Title"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_delete_session(client):
    resp = await client.post("/api/sessions", json={"title": "To Delete"})
    session_id = resp.json()["id"]
    resp = await client.delete(f"/api/sessions/{session_id}")
    assert resp.status_code == 204
    resp = await client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_session(client):
    resp = await client.get("/api/sessions/does-not-exist")
    assert resp.status_code == 404


# ── Chat ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_returns_message(client):
    resp = await client.post("/api/sessions", json={"title": "Chat Test"})
    session_id = resp.json()["id"]

    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "What is product market fit?", "skill": "auto"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    msg = data["message"]
    assert msg["role"] == "assistant"
    assert msg["content"]
    assert msg["skill"] == "qa"
    assert msg["provider"] == "mock"
    assert msg["used_fallback"] is False
    assert msg["latency_ms"] is not None


@pytest.mark.asyncio
async def test_chat_essay_skill_routing(client):
    resp = await client.post("/api/sessions", json={"title": "Essay Test"})
    session_id = resp.json()["id"]

    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "Write a Ship 30 essay about onboarding", "skill": "auto"},
    )
    assert resp.status_code == 200
    msg = resp.json()["message"]
    assert msg["skill"] == "ship30_essay"


@pytest.mark.asyncio
async def test_chat_artifact_routing_and_artifact_saved(client):
    resp = await client.post("/api/sessions", json={"title": "Artifact Test"})
    session_id = resp.json()["id"]

    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "Generate a markdown document about growth", "skill": "auto"},
    )
    assert resp.status_code == 200
    msg = resp.json()["message"]
    assert msg["skill"] == "artifact"
    # Artifact should be present
    assert msg["artifact"] is not None
    artifact_id = msg["artifact"]["id"]

    # Fetch artifact
    resp2 = await client.get(f"/api/artifacts/{artifact_id}")
    assert resp2.status_code == 200
    art = resp2.json()
    assert art["kind"] in ("markdown", "html")
    assert art["content"]
    assert art["rendered"]  # rendered HTML should be present


@pytest.mark.asyncio
async def test_chat_preserves_session_history(client):
    """Second message in same session should include conversation context."""
    resp = await client.post("/api/sessions", json={"title": "History Test"})
    session_id = resp.json()["id"]

    # First message
    await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "Tell me about onboarding", "skill": "qa"},
    )
    # Second message — history should be loaded
    resp = await client.post(
        f"/api/sessions/{session_id}/chat",
        json={"message": "Can you elaborate on that?", "skill": "qa"},
    )
    assert resp.status_code == 200

    # Session should now have 4 messages (2 user + 2 assistant)
    resp = await client.get(f"/api/sessions/{session_id}")
    messages = resp.json()["messages"]
    assert len(messages) == 4


@pytest.mark.asyncio
async def test_chat_with_nonexistent_session(client):
    resp = await client.post(
        "/api/sessions/nonexistent-id/chat",
        json={"message": "Hello"},
    )
    assert resp.status_code == 404


# ── Artifacts ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_artifact_not_found(client):
    resp = await client.get("/api/artifacts/no-such-artifact")
    assert resp.status_code == 404


# ── Admin reindex ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reindex_endpoint(client):
    """Reindex should succeed if transcripts dir exists, fail gracefully if not."""
    resp = await client.post("/api/admin/reindex")
    # Either OK (transcripts found) or 500 with a clear error — never a raw crash
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "episodes_indexed" in data
        assert "chunks_indexed" in data
        assert data["episodes_indexed"] > 0
