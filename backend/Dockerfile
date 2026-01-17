# Production Dockerfile for Backend
# Multi-stage build for optimal image size and security

# =============================================================================
# Builder Stage - Install dependencies and build wheels
# =============================================================================
FROM python:3.11-slim AS builder

# Install system build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install as wheels for faster production installs
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# =============================================================================
# Production Stage - Runtime image
# =============================================================================
FROM python:3.11-slim AS production

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash appuser

# Copy virtual environment and wheels from builder stage
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /wheels /wheels

# Install wheels into virtual environment
RUN /opt/venv/bin/pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Download spaCy model for NLP entity extraction and sentence boundary detection
RUN /opt/venv/bin/python -m spacy download en_core_web_sm

ENV PATH="/opt/venv/bin:$PATH"

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Copy only the source code (not tests, scripts, or development files)
COPY src/ ./src/

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start application
# App Runner scales instances, not workers, so use 1 worker
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
