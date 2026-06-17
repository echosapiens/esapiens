"""
app.py — Modal App ASGI Server & API Service Endpoints.

EchoSapiens orchestrator entry point. Deploys a scalable ASGI interface
under Modal and registers FastAPI endpoints for the multi-agent
bioinformatics pipeline.

Works both locally (``uvicorn echosapiens.app:web_app``) and on Modal
(``modal deploy echosapiens/app.py``). Modal is an optional import: when
absent, the FastAPI ``web_app`` still serves normally under uvicorn; the
Modal-specific decorators are simply skipped.
"""

import uuid
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .agents import EchoSapiensAgents
from .config import Settings, load_settings
from .gcs_manager import GCSManager
from .llm_client import BudgetLLMClient
from .sandbox_manager import SandboxManager
from .workflow_graph import build_workflow_graph

# Modal is optional for local-only development; required for Modal deployment.
try:
    import modal

    _MODAL_AVAILABLE = True
except ImportError:  # pragma: no cover — local-only fallback
    modal = None  # type: ignore[assignment]
    _MODAL_AVAILABLE = False

logger = structlog.get_logger()

# ── Modal Environment Definition ──────────────────────────────────────────

if _MODAL_AVAILABLE:
    assert modal is not None  # noqa: S101 — narrows type for Pyright
    image = (
        modal.Image.debian_slim(python_version="3.11")
        .pip_install(
            "langgraph>=0.2.0",
            "openai>=1.50.0",
            "google-cloud-storage>=2.18.0",
            "pydantic>=2.9.0",
            "pydantic-settings>=2.2.0",
            "fastapi>=0.115.0",
            "structlog>=24.0.0",
            "uvicorn>=0.30.0",
            "modal>=0.64.0",
        )
    )

    app = modal.App("echosapiens-api", image=image)

    # Register required workspace environment keys during startup.
    gcp_secret = modal.Secret.from_name("echosapiens-gcp-creds")
    llm_secret = modal.Secret.from_name("echosapiens-llm-keys")
else:
    image = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    gcp_secret = None  # type: ignore[assignment]
    llm_secret = None  # type: ignore[assignment]

# ── FastAPI Application ───────────────────────────────────────────────────

web_app = FastAPI(
    title="EchoSapiens API",
    version="7.0",
    description=(
        "Serverless multi-agent orchestration backend for bioinformatics "
        "IaaS — hypothesis formulation, workflow planning, and isolated "
        "ephemeral execution via Modal Sandboxes + GCS."
    ),
)


# ── API Validation Contracts ──────────────────────────────────────────────


class PipelineRequest(BaseModel):
    """Inbound contract for submitting a bioinformatics pipeline query."""

    query: str = Field(
        ...,
        example="Process paired-end FASTQ sequences through FastQC pipelines.",
    )
    error_handling_preference: str = Field(
        "agentic_self_correction",
        description="One of: agentic_self_correction, fail_fast_expose, "
        "human_in_the_loop.",
    )
    input_artifacts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Pre-uploaded GCS file metadata references (signed URLs).",
    )


class ManualOverrideRequest(BaseModel):
    """Inbound contract for resuming a paused pipeline after human review."""

    thread_id: str
    action: str = Field(..., description='"retry" or "abort".')
    instructions: str | None = Field(
        None,
        description="Corrective guidance injected into the next planning pass.",
    )


# ── Service Instantiation (lazy singletons) ───────────────────────────────
# Instantiated on first request, not at import time — this allows the module
# to be imported without credentials present (e.g. for testing, type checking,
# or when running under uvicorn without secrets configured yet). On Modal,
# secrets are injected as env vars before the container starts.

_settings: Settings | None = None
_gcs_mgr: GCSManager | None = None
_llm_client: BudgetLLMClient | None = None
_sb_mgr: SandboxManager | None = None
_agents: EchoSapiensAgents | None = None
_graph_app: Any = None


def get_services() -> tuple:
    """Lazily initialize and return all service singletons.

    Returns (settings, gcs_mgr, llm_client, sb_mgr, agents, graph_app).
    """
    global _settings, _gcs_mgr, _llm_client, _sb_mgr, _agents, _graph_app
    if _graph_app is None:
        _settings = load_settings()
        _gcs_mgr = GCSManager(_settings)
        _llm_client = BudgetLLMClient(_settings)
        _sb_mgr = SandboxManager(_settings, _gcs_mgr)
        _agents = EchoSapiensAgents(_llm_client, _sb_mgr)
        _graph_app = build_workflow_graph(_agents)
    return _settings, _gcs_mgr, _llm_client, _sb_mgr, _agents, _graph_app


# ── Endpoints ──────────────────────────────────────────────────────────────


@web_app.post("/v1/pipeline/run")
async def start_bio_pipeline(payload: PipelineRequest):
    """Submit a query into the LangGraph state machine and stream execution.

    Creates a fresh thread, builds the initial ``EchoSapiensState``, and
    invokes the compiled graph asynchronously. If the graph pauses for
    human-in-the-loop review, the checkpoint is preserved (via MemorySaver)
    and the caller receives a resumable ``thread_id``.
    """
    thread_id = f"thread_{uuid.uuid4().hex[:16]}"
    logger.info("submitting_pipeline_query", query=payload.query, thread_id=thread_id)

    # Populate initial Graph State parameters
    initial_state: dict[str, Any] = {
        "raw_query": payload.query,
        "formulated_hypothesis": None,
        "hypothesis_approved": False,
        "hypothesis_iterations": 0,
        "execution_plan": None,
        "planning_summary": None,
        "execution_results": [],
        "intermediate_artifacts": {},
        "retry_count": 0,
        "error_handling_preference": payload.error_handling_preference,
        "system_errors": [],
        "latest_step_in_error": None,
        "thread_id": thread_id,
        "session_status": "formulation",
        "input_artifacts": payload.input_artifacts,
    }

    config = {"configurable": {"thread_id": thread_id}}
    _, _, _, _, _, graph_app = get_services()

    try:
        final_state = await graph_app.ainvoke(initial_state, config=config)

        # Intercept interrupts (human_in_the_loop status pauses)
        if final_state.get("session_status") == "paused" or "human_input_request" in final_state:
            system_errors = final_state.get("system_errors") or []
            return {
                "thread_id": thread_id,
                "status": "awaiting_human_intervention",
                "system_error": system_errors[-1] if system_errors else None,
                "failed_step": final_state.get("latest_step_in_error"),
            }

        return {
            "thread_id": thread_id,
            "status": final_state.get("session_status"),
            "hypothesis": final_state.get("formulated_hypothesis"),
            "results": final_state.get("execution_results"),
            "output_artifacts": list(final_state.get("intermediate_artifacts", {}).values()),
            "errors": final_state.get("system_errors"),
        }

    except Exception as err:
        logger.exception("pipeline_fatal_failure", thread_id=thread_id)
        raise HTTPException(status_code=500, detail=f"Execution Failed: {str(err)}") from err


@web_app.post("/v1/pipeline/resume")
async def manual_override_pipeline(payload: ManualOverrideRequest):
    """Resume a paused pipeline after manual override.

    The graph's MemorySaver checkpointer restores the paused state by
    ``thread_id``; the override payload (action + instructions) is fed
    back into the graph for the next planning pass.
    """
    logger.info(
        "applying_manual_override",
        thread_id=payload.thread_id,
        action=payload.action,
    )
    config = {"configurable": {"thread_id": payload.thread_id}}

    override_input: dict[str, Any] = {
        "action": payload.action,
        "instructions": payload.instructions,
    }

    _, _, _, _, _, graph_app = get_services()

    try:
        # Resume processing dynamically inside existing Graph checkpoints
        state_update = await graph_app.ainvoke(override_input, config=config)

        return {
            "thread_id": payload.thread_id,
            "status": state_update.get("session_status"),
            "results": state_update.get("execution_results"),
            "output_artifacts": list(state_update.get("intermediate_artifacts", {}).values()),
        }
    except Exception as err:
        logger.exception(
            "manual_resumption_failed",
            thread_id=payload.thread_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Manual resumption failed: {str(err)}"
        ) from err


@web_app.get("/v1/health")
async def health_check():
    """Liveness probe — returns 200 when the ASGI server is up."""
    return {"status": "ok", "service": "echosapiens-api", "version": "7.0"}


# ── Modal web service attachment ──────────────────────────────────────────

if _MODAL_AVAILABLE:
    assert modal is not None  # noqa: S101 — narrows type for Pyright

    @app.function(secrets=[gcp_secret, llm_secret])
    @modal.asgi_app()
    def web_service():
        """Modal ASGI entry point — serves the FastAPI app on Modal."""
        return web_app
