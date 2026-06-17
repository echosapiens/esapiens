# ── Dockerfile — EchoSapiens Backend (local dev / optional VPS deploy) ──
#
# Builds a production-ready image that serves the FastAPI app via uvicorn.
# For Modal deployment, use `modal deploy echosapiens/app.py` instead.

FROM python:3.11-slim

WORKDIR /app

# ── 1. Copy project metadata and source ──
COPY pyproject.toml ./
COPY echosapiens/ /app/echosapiens/

# ── 2. Install the package and all declared dependencies ──
#    pyproject.toml lists langgraph, openai, google-cloud-storage,
#    pydantic, pydantic-settings, fastapi, uvicorn, structlog, and modal.
RUN pip install --no-cache-dir .

# ── 3. Run as non-root user for production security ──
RUN useradd --create-home --shell /bin/bash echosapiens
USER echosapiens

# ── 4. Expose the ASGI port ──
EXPOSE 8000

# ── 5. Serve the FastAPI app ──
#    web_app is the FastAPI instance exported from echosapiens/app.py.
#    --proxy-headers trusts X-Forwarded-* from any reverse proxy / ingress.
CMD ["uvicorn", "echosapiens.app:web_app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers"]