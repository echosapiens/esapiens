# EchoSapiens — Serverless Multi-Agent Orchestration Backend

A production-grade, modular, serverless multi-agent orchestration backend tailored for a **Bioinformatics + Infrastructure-as-a-Service (IaaS)** platform.

This system runs natively within **Modal.com**, leveraging **LangGraph** for structured conversation, workflow planning, and error routing. Heavy biological datasets never touch the orchestrator's state; instead, ephemeral **Modal Sandboxes** stream data directly to and from **Google Cloud Storage (GCS)** via pre-signed URLs. The execution layer uses OpenAI-compatible clients configured for budget reasoning models (such as Tencent HY3 / DeepSeek V4 Flash).

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │            MODAL.COM APP               │
                      │                                        │
                      │   ┌────────────────────────────────┐   │
                      │   │        FastAPI Endpoint        │   │
                      │   └────────────────▲───────────────┘   │
                      │                    │                   │
                      │   ┌────────────────▼───────────────┐   │
                      │   │    LangGraph State Machine     │   │
                      │   │       (MemorySaver Check)      │   │
                      │   └──────┬───────────────────▲─────┘   │
                      │          │                   │         │
                      └──────────┼───────────────────┼─────────┘
                                 │                   │
                     (Hypothesis, Planning,          │ Output Metadata
                       Execution Tasks)              │ (Signed URLs)
                                 │                   │
                                 ▼                   │
                     ┌───────────────────────────────┴─────────┐
                     │            EPHEMERAL SANDBOX            │
                     │          (modal.Sandbox.create)         │
                     │  - Runs quay.io Biocontainers image     │
                     │  - Streams direct to GCS (Zero-OOM)     │
                     └───────▲───────────────────────┬─────────┘
                             │                       │
                Download Input                       │ Upload Results
               via Signed GET                        │ via Signed PUT
                             │                       │
                     ┌───────┴───────────────────────▼─────────┐
                     │          GOOGLE CLOUD STORAGE           │
                     │      gs://echosapiens-artifacts/        │
                     └─────────────────────────────────────────┘
```

---

## Module List

| File | Description |
|------|-------------|
| `echosapiens/config.py` | Global settings & secrets via `pydantic-settings` — LLM endpoints, GCS config, sandbox limits, error-handling prefs. |
| `echosapiens/state.py` | LangGraph `EchoSapiensState` TypedDict, reducers (`append_logs`, `merge_metadata`), and structured metadata types (`GCSFileMetadata`, `PlanStep`, `ExecutionResult`). |
| `echosapiens/gcs_manager.py` | `GCSManager` — signed URL generation, upload/download orchestration, bucket lifecycle. |
| `echosapiens/llm_client.py` | `BudgetLLMClient` — OpenAI-compatible client wrapping Tencent HY3 / DeepSeek with token-budget tracking. |
| `echosapiens/sandbox_manager.py` | `SandboxManager` — creates ephemeral Modal Sandboxes with CPU/memory limits, streams I/O to/from GCS. |
| `echosapiens/agents.py` | `EchoSapiensAgents` — LangGraph node functions: hypothesis formulation, workflow planning, isolated execution. |
| `echosapiens/error_handler.py` | `ErrorInterventionRouter` — static methods for routing errors: self-correction, human checkpoint, fail-fast. |
| `echosapiens/workflow_graph.py` | `build_workflow_graph()` — assembles the compiled LangGraph DAG with `MemorySaver` checkpointer. |
| `echosapiens/app.py` | Modal + FastAPI entry point — `POST /v1/pipeline/run`, `POST /v1/pipeline/resume`, `GET /v1/health`. |

---

## Setup

### Prerequisites

- Python ≥ 3.11
- A Modal.com account (for serverless deployment)
- A GCP project with a Cloud Storage bucket and a service account JSON (Storage Object Admin)
- An LLM API key for an OpenAI-compatible endpoint (DeepSeek / Tencent HY3 / OpenRouter)

### 1. Clone & install locally

```bash
git clone <repo-url>
cd Esapiens-Sprint-7

# Create a virtualenv and install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment (`.env`)

Create a `.env` file in the project root for local development:

```bash
# LLM settings
LLM_API_KEY="sk-..."
LLM_BASE_URL="https://api.lkeap.cloud.tencent.com/v1"
LLM_MODEL="deepseek-v4-flash"

# GCS settings
GCP_PROJECT_ID="your-gcp-project-id"
GCS_BUCKET_NAME="echosapiens-artifacts"

# Sandbox defaults (optional overrides)
SANDBOX_DEFAULT_CPU=2.0
SANDBOX_DEFAULT_MEMORY_MB=4096
SANDBOX_TIMEOUT_SECONDS=1800

# Workflow orchestration
ERROR_HANDLING_PREFERENCE="agentic_self_correction"
MAX_AGENTIC_RETRIES=3
```

For GCS authentication locally, set `GOOGLE_APPLICATION_CREDENTIALS` to the path of your service account JSON:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa_key.json"
```

### 3. Register Modal secrets

Create the required secrets in your Modal account:

```bash
# Register LLM keys (DeepSeek / Tencent)
modal secret create echosapiens-llm-keys \
  LLM_API_KEY="sk-..." \
  LLM_BASE_URL="https://api.lkeap.cloud.tencent.com/v1" \
  LLM_MODEL="deepseek-v4-flash"

# Register GCP service account credentials (Storage Object Admin on target bucket)
modal secret create echosapiens-gcp-creds \
  GCP_PROJECT_ID="your_proj_id" \
  GCS_BUCKET_NAME="your_bucket" \
  GOOGLE_APPLICATION_CREDENTIALS="/keys/sa_key.json"
```

### 4. Deploy

**On Modal (serverless):**

```bash
modal deploy echosapiens/app.py
```

**Locally via uvicorn (dev):**

```bash
uvicorn echosapiens.app:web_app --host 0.0.0.0 --port 8000 --reload
```

**Locally via Docker (optional VPS):**

```bash
docker build -t echosapiens-api .
docker run -p 8000:8000 --env-file .env -e GOOGLE_APPLICATION_CREDENTIALS=/app/sa_key.json -v /path/to/sa_key.json:/app/sa_key.json:ro echosapiens-api
```

---

## API Endpoints

### `POST /v1/pipeline/run`

Submits a bioinformatics query into the LangGraph state machine. Returns a `thread_id` plus either completed results or a pause signal for human review.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `string` | ✅ | Natural-language pipeline request. |
| `error_handling_preference` | `string` | ❌ | One of `agentic_self_correction` (default), `fail_fast_expose`, `human_in_the_loop`. |
| `input_artifacts` | `list[object]` | ❌ | Pre-uploaded GCS file metadata with signed URLs. |

### `POST /v1/pipeline/resume`

Resumes a paused pipeline after human review. Restores the checkpointed state via `thread_id` and injects corrective instructions.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `thread_id` | `string` | ✅ | Thread ID from the original `/run` response. |
| `action` | `string` | ✅ | `"retry"` or `"abort"`. |
| `instructions` | `string` | ❌ | Corrective guidance for the next planning pass. |

### `GET /v1/health`

Liveness probe — returns `{"status": "ok", "service": "echosapiens-api", "version": "7.0"}`.

---

## Error Handling Modes

EchoSapiens supports three error-handling strategies, set per-request via the `error_handling_preference` field:

### 1. `agentic_self_correction` (default)

The agent automatically updates parameters and retries execution, self-correcting up to a maximum of `MAX_AGENTIC_RETRIES` (default 3) times before terminating. If all retries fail, the pipeline returns the accumulated error log.

```bash
curl -X POST "https://your-modal-workspace-endpoint.modal.run/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Synthesize a BAM analysis pipeline targeting a corrupted BAM mapping standard.",
    "error_handling_preference": "agentic_self_correction",
    "input_artifacts": [
      {
        "file_name": "corrupted_targets.bam",
        "gcs_uri": "gs://echosapiens-artifacts/testing/corrupted_targets.bam",
        "signed_download_url": "https://storage.googleapis.com/...signed_get...",
        "size_bytes": 145022
      }
    ]
  }'
```

### 2. `fail_fast_expose`

Execution terminates immediately on the first non-zero sandbox exit code. The full error detail is returned straight to the caller with no retry attempts.

```bash
curl -X POST "https://your-modal-workspace-endpoint.modal.run/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Align genomic reads to hg38 reference databases.",
    "error_handling_preference": "fail_fast_expose",
    "input_artifacts": []
  }'
```

### 3. `human_in_the_loop`

The pipeline pauses on error, and the state checkpoint is saved via `MemorySaver`. The caller receives `status: "awaiting_human_intervention"` with the error detail. The pipeline can be resumed manually with corrected instructions.

```bash
# Step 1: Submit processing that generates an interrupt checkpoint
curl -X POST "https://your-modal-workspace-endpoint.modal.run/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Analyze mutated sequences with incomplete target coordinates.",
    "error_handling_preference": "human_in_the_loop"
  }'

# Expected response:
# {
#   "thread_id": "thread_abc123xyz...",
#   "status": "awaiting_human_intervention",
#   "system_error": "FastQC failed with error exit status code 1"
# }

# Step 2: Manually resume execution with corrected processing instructions
curl -X POST "https://your-modal-workspace-endpoint.modal.run/v1/pipeline/resume" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_abc123xyz...",
    "action": "retry",
    "instructions": "Replace input mapping references utilizing clean reference indices."
  }'
```

---

## License

Proprietary — EchoSapiens. All rights reserved.