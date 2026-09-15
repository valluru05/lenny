# ──────────────────────────────────────────────────────────────────────────────
# Lenny Growth Assistant — Backend Dockerfile
# Multi-stage build: builder installs deps, runner is lean image.
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for some packages (e.g. rank-bm25, greenlet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runner ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS runner

LABEL maintainer="Lenny Growth Assistant"
LABEL description="AI-powered assistant grounded in Lenny's Podcast transcripts"

# Keeps Python from buffering stdout/stderr (important for structured logs)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install runtime OS deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application source
COPY app/ ./app/

# Data directory (transcripts + index will be mounted or pre-copied)
RUN mkdir -p /app/data/transcripts

# Non-root user for security
RUN useradd -m -u 1000 lenny && chown -R lenny:lenny /app
USER lenny

# Health check — uses /api/health (returns 200 even when degraded, 
# so Docker doesn't restart for missing index)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || exit 1

EXPOSE 8000

# Entrypoint: uvicorn with configurable workers
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "warning"]
