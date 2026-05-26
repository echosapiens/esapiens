# ── Backend Dockerfile ──────────────────────────────────────────────────────
# E.sapiens v2 — FastAPI + LangGraph agent
# Uses slim Python 3.12 image for a minimal footprint.
# ────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (none needed currently, but keep slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ /app/

# Copy bioSkills (build context is repo root, so bioSkills/ is accessible)
COPY bioSkills /app/bioSkills

# Expose FastAPI port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
