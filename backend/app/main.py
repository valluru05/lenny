"""
main.py — FastAPI application entry point.
Wires up: lifespan (db init + index load), middleware (CORS, request-ID),
global exception handlers, and all API routers.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_conf import configure_logging, get_logger
from app.schemas import ErrorDetail, ErrorResponse

# Configure logging before anything else
configure_logging(debug=settings.debug)
log = get_logger("main")


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: init DB tables + attempt to load BM25 index. Shutdown: close engine."""
    log.info("startup", app=settings.app_name, version=settings.app_version)

    # Init DB
    from app.db import init_db
    await init_db()
    log.info("db.initialized")

    # Attempt to load BM25 index (non-fatal if not built yet)
    try:
        from app.rag.index_store import IndexStore
        store = IndexStore(settings.bm25_index_path)
        if store.exists():
            store.load()
            app.state.index_store = store
            log.info("rag.index_loaded", path=settings.bm25_index_path)
        else:
            app.state.index_store = None
            log.warning(
                "rag.index_missing",
                detail="POST /api/admin/reindex to build",
            )
    except Exception as exc:
        app.state.index_store = None
        log.error("rag.index_load_failed", exc=str(exc))

    yield

    # Shutdown
    from app.db import close_db
    await close_db()
    log.info("shutdown")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request-ID middleware ────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Bind a unique request_id to structlog contextvars for the lifetime of this request."""
    request_id = str(uuid.uuid4())[:8]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)

    log.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handlers ────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", exc=str(exc), path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code="internal_error",
                message="An unexpected error occurred.",
                detail=str(exc) if settings.debug else None,
            )
        ).model_dump(),
    )


# ── Routers ─────────────────────────────────────────────────────────────────

from app.api.health import router as health_router        # noqa: E402
from app.api.sessions import router as sessions_router    # noqa: E402
from app.api.chat import router as chat_router            # noqa: E402
from app.api.artifacts import router as artifacts_router  # noqa: E402
from app.api.admin import router as admin_router          # noqa: E402

app.include_router(health_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
