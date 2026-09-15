"""
tests/conftest.py — Set environment variables before any app module is imported.

This runs before pytest collects or imports any test files,
ensuring pydantic-settings picks up the test configuration.
"""
import os
from pathlib import Path

# Compute absolute paths relative to this file
_TESTS_DIR = Path(__file__).parent
_BACKEND_DIR = _TESTS_DIR.parent
_REPO_DIR = _BACKEND_DIR.parent

# These must be set before `from app.xxx import ...` in any test file
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_lenny.db")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("BM25_INDEX_PATH", str(_REPO_DIR / "data" / "bm25_index.pkl"))
os.environ.setdefault("TRANSCRIPTS_DIR", str(_REPO_DIR / "data" / "transcripts"))
