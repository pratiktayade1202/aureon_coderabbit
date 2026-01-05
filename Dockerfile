# ==============================================================================
# AUREON RECONCILIATION PLATFORM - PRODUCTION DOCKERFILE
# ==============================================================================
# Multi-stage build for optimized image size
# Build: docker build -t aureon-backend .
# Run: docker run -p 8000:8000 --env-file .env aureon-backend
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build dependencies
# ------------------------------------------------------------------------------
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Production image
# ------------------------------------------------------------------------------
FROM python:3.11-slim as production

# Security: Create non-root user
RUN groupadd -r aureon && useradd -r -g aureon aureon

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create necessary directories
RUN mkdir -p /app/logs /app/temp && \
    chown -R aureon:aureon /app

# Switch to non-root user
USER aureon

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run with Gunicorn for production
CMD ["sh", "-c", "gunicorn backend.main:app --bind 0.0.0.0:${PORT} --workers ${WORKERS:-4} --worker-class uvicorn.workers.UvicornWorker --timeout 120 --access-logfile - --error-logfile -"]

# ------------------------------------------------------------------------------
# Stage 3: Development image (optional)
# Build with: docker build --target development -t aureon-dev .
# ------------------------------------------------------------------------------
FROM production as development

USER root

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

USER aureon

ENV ENVIRONMENT=development

# Use uvicorn with reload for development
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT} --reload"]
