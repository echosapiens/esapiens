# EchoSapiens Sprint 6 — Serverless Multi-Agent Orchestration Backend

A production-grade, modular, serverless multi-agent orchestration backend tailored for a Bioinformatics + Infrastructure-as-a-Service (IaaS) platform. 

This blueprint runs natively within **Modal.com**, leveraging **LangGraph** for structured conversation, workflow planning, and error routing. Heavy biological datasets never touch the orchestrator's state; instead, ephemeral **Modal Sandboxes** stream data directly to and from **Google Cloud Storage (GCS)** via pre-signed URLs. The execution layer utilizes OpenAI-compatible clients configured for budget reasoning models (such as Tencent HY3 / DeepSeek V4 Flash).

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

## Code Blueprint

### 1. `config.py`
This module manages global configuration, timeouts, environment secrets, and runtime parameters.

```python
"""
config.py - Global Environment, Settings, and Secrets Configuration
"""

import os
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ErrorHandlingPreference = Literal["agentic_self_correction", "fail_fast_expose", "human_in_the_loop"]

class Settings(BaseSettings):
    """
    Global settings for the EchoSapiens execution engine.
    Ensures safe, production-grade credentials loading.
    """
    # LLM Settings (Optimized for Tencent HY3 / DeepSeek V4 Flash)
    llm_api_key: str = Field(..., validation_alias="LLM_API_KEY")
    llm_base_url: str = Field("https://api.lkeap.cloud.tencent.com/v1", validation_alias="LLM_BASE_URL")
    llm_model: str = Field("deepseek-v4-flash", validation_alias="LLM_MODEL")
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    # GCS Storage Configuration
    gcs_bucket_name: str = Field(..., validation_alias="GCS_BUCKET_NAME")
    gcp_project_id: str = Field(..., validation_alias="GCP_PROJECT_ID")
    gcs_signed_url_ttl: int = 3600  # 1 hour default

    # Sandbox Compute Configuration
    sandbox_default_cpu: float = 2.0
    sandbox_default_memory_mb: int = 4096
    sandbox_timeout_seconds: int = 1800  # 30-minute limit per sandbox execution

    # Workflow Orchestration
    error_handling_preference: ErrorHandlingPreference = "agentic_self_correction"
    max_agentic_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

def load_settings() -> Settings:
    """Returns verified and loaded system setting variables."""
    # Instantiated on execution and validated by Pydantic
    return Settings()
```

### 2. `state.py`
This module defines the schema of the LangGraph state machine. It handles appending execution lists and storing file metadata without polluting the graph with heavy datasets.

```python
"""
state.py - LangGraph State Schemas for State Machine Verification
"""

from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict
import operator

# Reducers for Merging Complex State Nodes
def append_logs(left: List[str], right: List[str]) -> List[str]:
    return left + right

def merge_metadata(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return {**left, **right}

class GCSFileMetadata(TypedDict):
    """Heavy bioinformatics file metadata reference."""
    file_name: str
    gcs_uri: str
    signed_download_url: str
    size_bytes: int
    content_type: str

class PlanStep(TypedDict):
    """A highly granular structured execution pipeline step."""
    step_id: int
    name: str
    tool_image: str  # e.g., "quay.io/biocontainers/samtools:1.20--h8b25389_0"
    command_template: str  # CLI Command execution pattern
    expected_output_files: List[str]

class ExecutionResult(TypedDict):
    """Execution feedback parsed instantly from the sandbox endpoint."""
    step_id: int
    exit_code: int
    stdout_summary: str
    stderr_summary: str
    uploaded_outputs: List[GCSFileMetadata]
    success: bool

class EchoSapiensState(TypedDict):
    """
    State machine state representation for the bioinformatics pipelines.
    Reducers ensure incremental updates without destroying previous states.
    """
    # Step 1: Hypothesis Formulation (Interactive)
    raw_query: str
    formulated_hypothesis: Optional[str]
    hypothesis_approved: bool
    hypothesis_iterations: int

    # Step 2: Scientific Workflow Planning
    execution_plan: Optional[List[PlanStep]]
    planning_summary: Optional[str]

    # Step 3: Isolated Ephemeral Core Execution
    execution_results: Annotated[List[ExecutionResult], operator.add]
    intermediate_artifacts: Annotated[Dict[str, GCSFileMetadata], merge_metadata]
    
    # Global Execution State
    retry_count: int
    error_handling_preference: Literal["agentic_self_correction", "fail_fast_expose", "human_in_the_loop"]
    system_errors: Annotated[List[str], append_logs]
    latest_step_in_error: Optional[int]
    
    # Technical Execution Metadata
    thread_id: str
    session_status: Literal["formulation", "planning", "running", "paused", "completed", "failed"]
```

### 3. `gcs_manager.py`
Enables direct-to-cloud streams for large-scale genetic processing. Generates high-speed GET and PUT pre-signed V4 signatures, completely shifting performance bottlenecks away from the central supervisor node.

```python
"""
gcs_manager.py - High-Performance GCS Signed URL Stream Architecture
"""

import datetime
from typing import Dict, Any, Optional
from google.cloud import storage
import structlog

from .config import Settings

logger = structlog.get_logger()

class GCSManager:
    """
    Manages direct, non-proxied data streaming between Ephemeral Sandboxes and GCS.
    Ensures that orchestrator memory never exceeds baseline thresholds.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        # Falls back cleanly onto ADC / Modal injected Service Account secrets
        self.storage_client = storage.Client(project=self.settings.gcp_project_id)
        self.bucket = self.storage_client.bucket(self.settings.gcs_bucket_name)

    def generate_download_signed_url(self, blob_name: str) -> str:
        """Generates reading signatures directly for target biocontainers."""
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=self.settings.gcs_signed_url_ttl),
            method="GET",
        )
        return url

    def generate_upload_signed_url(self, blob_name: str, content_type: str = "application/octet-stream") -> str:
        """Generates payload writing signatures directly for target biocontainers."""
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=self.settings.gcs_signed_url_ttl),
            method="PUT",
            content_type=content_type,
        )
        return url

    def get_blob_metadata(self, blob_name: str) -> Optional[Dict[str, Any]]:
        """Extracts statistical metadata for analytical record keeping."""
        blob = self.bucket.get_blob(blob_name)
        if not blob:
            return None
        return {
            "file_name": os.path.basename(blob_name),
            "gcs_uri": f"gs://{self.settings.gcs_bucket_name}/{blob_name}",
            "size_bytes": blob.size,
            "content_type": blob.content_type or "application/octet-stream",
        }
```

### 4. `llm_client.py`
Interfaces with OpenAI-compatible endpoints configured to route queries through budget LLM reasoning models.

```python
"""
llm_client.py - Budget-Model OpenAI-Compatible Verification Client
"""

from typing import Any, Dict, List, Type
import json
from openai import OpenAI
from pydantic import BaseModel
import structlog

from .config import Settings

logger = structlog.get_logger()

class BudgetLLMClient:
    """
    Custom client wrapper for OpenAI-compatible budget model execution.
    Features robust structured JSON validation and schema injection.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url
        )

    def call_structured(self, messages: List[Dict[str, str]], response_schema: Type[BaseModel]) -> BaseModel:
        """
        Enforces structured JSON extraction conforming strictly to validation models.
        """
        system_instruction = (
            f"You are a scientific computational agent. Return JSON matching this schema: "
            f"{json.dumps(response_schema.model_json_schema())}"
        )
        
        # Inject validation schema at index 0
        messages_with_schema = [{"role": "system", "content": system_instruction}] + messages

        logger.info("llm_call_initiated", model=self.settings.llm_model)

        response = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages_with_schema,
            response_format={"type": "json_object"},
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens
        )

        content = response.choices[0].message.content
        logger.debug("llm_call_completed", response_length=len(content or ""))
        
        # Validates and marshalls output directly into targeted Pydantic Models
        return response_schema.model_validate_json(content)
```

### 5. `sandbox_manager.py`
Launches secure, ephemeral sandboxes running bioinformatics workflows. To execute steps, it signs data locations beforehand, passes the access parameters down, and forces-streams sandbox output back to GCS without passing file buffers through host runtime memory.

```python
"""
sandbox_manager.py - Ephemeral Micro-Compute Sandbox Orchestration Layer
"""

import modal
import structlog
from typing import Dict, Any, List
import uuid

from .config import Settings
from .gcs_manager import GCSManager, GCSFileMetadata

logger = structlog.get_logger()

# Shared Global App reference specifically designated for sandboxing operations
sandbox_app = modal.App.lookup("echosapiens-sandboxes", create_if_missing=True)

class SandboxManager:
    """
    Maintains complete isolation over sandbox lifecycles.
    Streams input sequences inside the virtual environments via pre-signed GETs, 
    and handles uploads back to GCS via pre-signed PUT signature requests.
    """
    def __init__(self, settings: Settings, gcs_manager: GCSManager):
        self.settings = settings
        self.gcs = gcs_manager

    def execute_isolated_step(
        self, 
        step_id: int, 
        tool_image: str, 
        command_template: str, 
        input_files: List[GCSFileMetadata], 
        expected_outputs: List[str]
    ) -> Dict[str, Any]:
        """
        Spawns a highly-confined sandbox on Modal to run a bioinformatics tool safely.
        """
        logger.info("spawning_sandbox", step_id=step_id, tool_image=tool_image)
        session_token = uuid.uuid4().hex[:12]
        
        # 1. Prepare sandboxed paths inside target volumes
        work_dir = f"/work_{session_token}"
        input_dir = f"{work_dir}/inputs"
        output_dir = f"{work_dir}/outputs"
        
        # Prepare environment variables dynamically
        environment_vars = {}
        download_command = "mkdir -p " + input_dir + " " + output_dir + " && "
        
        # Map input files internally inside sandbox environments via signed downloads
        for idx, file_meta in enumerate(input_files):
            sandbox_input_path = f"{input_dir}/{file_meta['file_name']}"
            download_command += f"curl -sL '{file_meta['signed_download_url']}' -o {sandbox_input_path} && "
            environment_vars[f"INPUT_FILE_{idx}"] = sandbox_input_path

        # Resolve command arguments based on internal storage mappings
        resolved_command = command_template
        for idx, file_meta in enumerate(input_files):
            resolved_command = resolved_command.replace(f"{{{{INPUT_{idx}}}}}", f"{input_dir}/{file_meta['file_name']}")
        
        # Replace expected outputs dynamically matching workspace definitions
        for output_file in expected_outputs:
            resolved_command = resolved_command.replace(f"{{{{OUTPUT_{output_file}}}}}", f"{output_dir}/{output_file}")

        # Combine download, execution, and upload sequences
        combined_exec_expr = download_command + f"cd {work_dir} && {resolved_command}"
        
        # Formulate pre-signed PUT handlers to enable output streaming directly out of the sandbox
        upload_map: Dict[str, str] = {}
        for output_file in expected_outputs:
            gcs_dest_blob = f"runs/{session_token}/step_{step_id}/{output_file}"
            signed_put_url = self.gcs.generate_upload_signed_url(gcs_dest_blob)
            upload_map[output_file] = signed_put_url
            
            # Chain binary push operations
            combined_exec_expr += f" && curl -X PUT -H 'Content-Type: application/octet-stream' --upload-file {output_dir}/{output_file} '{signed_put_url}'"

        # Safe isolation: enforce strict runtime limitations per task
        img = modal.Image.from_registry(tool_image, add_python="3.11").apt_install("curl", "bash")
        
        sb = modal.Sandbox.create(
            "bash",
            "-c",
            combined_exec_expr,
            image=img,
            app=sandbox_app,
            cpu=self.settings.sandbox_default_cpu,
            memory=self.settings.sandbox_default_memory_mb,
            timeout=self.settings.sandbox_timeout_seconds,
            env=environment_vars
        )
        
        # Block gracefully until processing is complete
        sb.wait()
        
        exit_code = sb.returncode
        stdout = sb.stdout.read()
        stderr = sb.stderr.read()

        logger.info("sandbox_execution_concluded", step_id=step_id, exit_code=exit_code)

        # Build output metadata structures to return to the graph
        output_file_manifest: List[GCSFileMetadata] = []
        if exit_code == 0:
            for output_file in expected_outputs:
                gcs_dest_blob = f"runs/{session_token}/step_{step_id}/{output_file}"
                download_signed = self.gcs.generate_download_signed_url(gcs_dest_blob)
                
                output_file_manifest.append({
                    "file_name": output_file,
                    "gcs_uri": f"gs://{self.settings.gcs_bucket_name}/{gcs_dest_blob}",
                    "signed_download_url": download_signed,
                    "size_bytes": 0  # Retrieved dynamically by backend downstream pipelines later
                })

        return {
            "exit_code": exit_code,
            "stdout_summary": stdout[-2000:],  # Tail logs
            "stderr_summary": stderr[-2000:],
            "output_file_manifest": output_file_manifest,
            "success": exit_code == 0
        }
```

### 6. `agents.py`
This module defines the structured agents designed to operate in sequence.

```python
"""
agents.py - LangGraph Multi-Agent Node Execution Defs
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
import structlog

from .state import EchoSapiensState, PlanStep
from .llm_client import BudgetLLMClient
from .sandbox_manager import SandboxManager

logger = structlog.get_logger()

# ── Step 1: Scientific Hypothesis Verification Model ──
class HypothesisResponseSchema(BaseModel):
    formulated_hypothesis: str = Field(..., description="The highly specific, testable scientific formulation.")
    required_iterations: int = Field(..., description="Number of alignment corrections implemented.")
    approved: bool = Field(..., description="Flags if a valid hypothesis is ready for execution mapping.")

# ── Step 2: Scientific Plan Synthesis Model ──
class PlanStepModel(BaseModel):
    step_id: int
    name: str
    tool_image: str
    command_template: str
    expected_output_files: List[str]

class PlanningResponseSchema(BaseModel):
    execution_plan: List[PlanStepModel]
    planning_summary: str

class EchoSapiensAgents:
    """
    Encapsulates sequential agent behavior.
    """
    def __init__(self, llm: BudgetLLMClient, sandbox: SandboxManager):
        self.llm = llm
        self.sandbox = sandbox

    def hypothesis_formulation_agent(self, state: EchoSapiensState) -> Dict[str, Any]:
        """
        Step 1 Agent Node.
        Formulates raw prompt requests into highly testable assumptions.
        """
        logger.info("hypothesis_agent_execution_started", thread_id=state.get("thread_id"))
        
        prompt = [
            {"role": "system", "content": "You are a bioinformatics lead modeling strict scientific hypotheses."},
            {"role": "user", "content": f"Formulate and validate this query into research hypotheses: {state['raw_query']}"}
        ]
        
        llm_response: HypothesisResponseSchema = self.llm.call_structured(prompt, HypothesisResponseSchema)
        
        return {
            "formulated_hypothesis": llm_response.formulated_hypothesis,
            "hypothesis_approved": llm_response.approved,
            "hypothesis_iterations": state.get("hypothesis_iterations", 0) + 1,
            "session_status": "formulation"
        }

    def workflow_planning_agent(self, state: EchoSapiensState) -> Dict[str, Any]:
        """
        Step 2 Agent Node.
        Synthesizes execution paths mapped directly to Docker containers on quay.io.
        """
        logger.info("planning_agent_execution_initiated", thread_id=state.get("thread_id"))
        
        prompt = [
            {"role": "system", "content": "Produce a robust plan mapped directly to quay.io Docker containers."},
            {"role": "user", "content": f"Hypothesis validated: {state['formulated_hypothesis']}. Plan execution accordingly."}
        ]

        llm_response: PlanningResponseSchema = self.llm.call_structured(prompt, PlanningResponseSchema)
        
        # Map step attributes to list of step dictionaries
        steps = [
            PlanStep(
                step_id=s.step_id,
                name=s.name,
                tool_image=s.tool_image,
                command_template=s.command_template,
                expected_output_files=s.expected_output_files
            ) for s in llm_response.execution_plan
        ]

        return {
            "execution_plan": steps,
            "planning_summary": llm_response.planning_summary,
            "session_status": "planning"
        }

    def isolated_execution_agent(self, state: EchoSapiensState) -> Dict[str, Any]:
        """
        Step 3 Agent Node.
        Orchestrates direct modal container configurations sequentially.
        """
        logger.info("isolated_execution_agent_started", thread_id=state.get("thread_id"))
        
        plans: List[PlanStep] = state["execution_plan"] or []
        execution_log = []
        artifacts = {}
        
        for step in plans:
            # Map parameters utilizing metadata structures
            result = self.sandbox.execute_isolated_step(
                step_id=step["step_id"],
                tool_image=step["tool_image"],
                command_template=step["command_template"],
                input_files=list(state.get("input_artifacts", [])),
                expected_outputs=step["expected_output_files"]
            )
            
            execution_log.append({
                "step_id": step["step_id"],
                "exit_code": result["exit_code"],
                "stdout_summary": result["stdout_summary"],
                "stderr_summary": result["stderr_summary"],
                "uploaded_outputs": result["output_file_manifest"],
                "success": result["success"]
            })
            
            # Map tracking references to outputs if successful
            if result["success"]:
                for out_meta in result["output_file_manifest"]:
                    artifacts[out_meta["file_name"]] = out_meta
            else:
                # Intercept non-zero execution exit streams immediately
                return {
                    "execution_results": execution_log,
                    "intermediate_artifacts": artifacts,
                    "latest_step_in_error": step["step_id"],
                    "session_status": "running",
                    "system_errors": [f"Step {step['step_id']} failed with code {result['exit_code']}"]
                }
                
        return {
            "execution_results": execution_log,
            "intermediate_artifacts": artifacts,
            "latest_step_in_error": None,
            "session_status": "completed"
        }
```

### 7. `error_handler.py`
This module evaluates sandboxed execution conditions and dynamically handles failures according to the global `error_handling_preference`.

```python
"""
error_handler.py - Error Intervention Routing Engine
"""

from typing import Dict, Any, Literal
from langgraph.types import interrupt
import structlog

from .state import EchoSapiensState

logger = structlog.get_logger()

class ErrorInterventionRouter:
    """
    Evaluates sandbox execution outputs and applies error mitigation strategies.
    Supports self-correction, strict technical exits, and administrative interrupts.
    """
    
    @staticmethod
    def route_error_state(state: EchoSapiensState) -> Literal["planning_retry", "fail_fast_exit", "human_review_boundary", "proceed"]:
        """
        Infers direction pathways from runtime environments.
        """
        if not state.get("system_errors") or state.get("latest_step_in_error") is None:
            return "proceed"

        preference = state.get("error_handling_preference", "agentic_self_correction")
        retry_count = state.get("retry_count", 0)

        logger.warn("error_routing_evaluation", preference=preference, retry_count=retry_count)

        if preference == "agentic_self_correction":
            if retry_count < 3:
                return "planning_retry"
            return "fail_fast_exit"

        elif preference == "human_in_the_loop":
            return "human_review_boundary"

        # Default fallback strategy is immediate exit exposure
        return "fail_fast_exit"

    @staticmethod
    def execute_self_correction(state: EchoSapiensState) -> Dict[str, Any]:
        """
        Increments internal failure counter and triggers pipeline recalculations.
        """
        logger.info("applying_agentic_self_correction", current_retries=state.get("retry_count"))
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            # Clears standard system error properties for re-evaluation runs
            "system_errors": []
        }

    @staticmethod
    def human_checkpoint_interrupter(state: EchoSapiensState) -> Dict[str, Any]:
        """
        Halts the active state machine using LangGraph's native interrupt interface.
        """
        logger.warn("human_checkpoint_activated", thread_id=state.get("thread_id"))
        
        # Build state snapshot payload for the administrator
        admin_payload = {
            "error_message": state.get("system_errors", ["Unknown sandbox failure"])[-1],
            "step_id": state.get("latest_step_in_error"),
            "suggestion": "Overwrite biological criteria or parameters to resolve pipeline blockages."
        }
        
        # HALT: pause progress until manual action is applied via API.
        user_override: Dict[str, Any] = interrupt(admin_payload)
        
        logger.info("manual_override_received", decision=user_override.get("action"))
        
        if user_override.get("action") == "retry":
            return {
                "retry_count": state.get("retry_count", 0) + 1,
                "system_errors": [],
                "error_handling_preference": "agentic_self_correction"  # Temporarily resume self-correction
            }
        
        # Administrative Abort request
        return {
            "session_status": "failed",
            "system_errors": ["Aborted manually by administrative overrides."]
        }
```

### 8. `workflow_graph.py`
Connects the nodes, edges, and decision branches into a complete LangGraph DAG state machine.

```python
"""
workflow_graph.py - LangGraph Functional Workflow DAG Configuration
"""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import EchoSapiensState
from .agents import EchoSapiensAgents
from .error_handler import ErrorInterventionRouter

def build_workflow_graph(agents: EchoSapiensAgents) -> StateGraph:
    """
    Constructs a compiled multi-agent state machine.
    """
    builder = StateGraph(EchoSapiensState)

    # ── Node Definitions ──
    builder.add_node("formulate_hypothesis", agents.hypothesis_formulation_agent)
    builder.add_node("plan_workflow", agents.workflow_planning_agent)
    builder.add_node("execute_isolated_workloads", agents.isolated_execution_agent)
    
    builder.add_node("agentic_correction", ErrorInterventionRouter.execute_self_correction)
    builder.add_node("human_interruption_checkpoint", ErrorInterventionRouter.human_checkpoint_interrupter)

    # ── Workflow Edges ──
    builder.add_edge(START, "formulate_hypothesis")
    builder.add_edge("formulate_hypothesis", "plan_workflow")
    builder.add_edge("plan_workflow", "execute_isolated_workloads")

    # ── Conditional Error Router Deciders ──
    def route_post_execution(state: EchoSapiensState) -> Literal["agentic_correction", "human_interruption_checkpoint", "fail_fast_terminate", "complete_run"]:
        decision = ErrorInterventionRouter.route_error_state(state)
        
        if decision == "planning_retry":
            return "agentic_correction"
        elif decision == "human_review_boundary":
            return "human_interruption_checkpoint"
        elif decision == "fail_fast_exit":
            return "fail_fast_terminate"
        return "complete_run"

    builder.add_conditional_edges(
        "execute_isolated_workloads",
        route_post_execution,
        {
            "agentic_correction": "agentic_correction",
            "human_interruption_checkpoint": "human_interruption_checkpoint",
            "fail_fast_terminate": END,
            "complete_run": END
        }
    )

    # Error recovery loopback edges returning focus back onto workflow logic execution nodes
    builder.add_edge("agentic_correction", "plan_workflow")
    builder.add_edge("human_interruption_checkpoint", "plan_workflow")

    # Native Memory Saver Checkpointer handles state recovery during human-in-the-loop manual overrides
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
```

### 9. `app.py`
The orchestrator entry point. Deploys standard, highly scalable ASGI interfaces under **Modal** environments and registers FastAPI endpoints.

```python
"""
app.py - Modal App ASGI Server & API Service Endpoints
"""

import modal
import uuid
import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from .config import load_settings
from .gcs_manager import GCSManager
from .llm_client import BudgetLLMClient
from .sandbox_manager import SandboxManager
from .agents import EchoSapiensAgents
from .workflow_graph import build_workflow_graph

logger = structlog.get_logger()

# ── Modal Environment Definition ──
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "langgraph>=0.2.0",
        "openai>=1.50.0",
        "google-cloud-storage>=2.18.0",
        "pydantic-settings>=2.2.0",
        "fastapi>=0.115.0",
        "structlog>=24.0.0",
        "uvicorn>=0.30.0"
    )
)

app = modal.App("echosapiens-api", image=image)

# Register required workspace environment keys during startup
gcp_secret = modal.Secret.from_name("echosapiens-gcp-creds")
llm_secret = modal.Secret.from_name("echosapiens-llm-keys")

web_app = FastAPI(title="EchoSapiens API", version="6.0")

# ── API Validation Contracts ──
class PipelineRequest(BaseModel):
    query: str = Field(..., example="Process paired-end FASTQ sequences through FastQC pipelines.")
    error_handling_preference: str = Field("agentic_self_correction")
    input_artifacts: List[Dict[str, Any]] = Field(default_factory=list)

class ManualOverrideRequest(BaseModel):
    thread_id: str
    action: str  # "retry" or "abort"
    instructions: Optional[str] = None

# Instantiate services once per thread container
settings = load_settings()
gcs_mgr = GCSManager(settings)
llm_client = BudgetLLMClient(settings)
sb_mgr = SandboxManager(settings, gcs_mgr)
agents = EchoSapiensAgents(llm_client, sb_mgr)
graph_app = build_workflow_graph(agents)

@web_app.post("/v1/pipeline/run")
async def start_bio_pipeline(payload: PipelineRequest):
    """
    Submits a sequence into the backend State Machine and monitors execution.
    """
    thread_id = f"thread_{uuid.uuid4().hex[:16]}"
    logger.info("submitting_pipeline_query", query=payload.query, thread_id=thread_id)

    # Populate initial Graph State parameters
    initial_state = {
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
        "input_artifacts": payload.input_artifacts
    }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = graph_app.invoke(initial_state, config=config)
        
        # Intercept interrupts (human_in_the_loop status pauses)
        if final_state.get("session_status") == "paused" or "human_input_request" in final_state:
            return {
                "thread_id": thread_id,
                "status": "awaiting_human_intervention",
                "system_error": final_state.get("system_errors")[-1],
                "failed_step": final_state.get("latest_step_in_error")
            }

        return {
            "thread_id": thread_id,
            "status": final_state.get("session_status"),
            "hypothesis": final_state.get("formulated_hypothesis"),
            "results": final_state.get("execution_results"),
            "output_artifacts": list(final_state.get("intermediate_artifacts", {}).values()),
            "errors": final_state.get("system_errors")
        }

    except Exception as err:
        logger.exception("pipeline_fatal_failure", thread_id=thread_id)
        raise HTTPException(status_code=500, detail=f"Execution Failed: {str(err)}")

@web_app.post("/v1/pipeline/resume")
async def manual_override_pipeline(payload: ManualOverrideRequest):
    """
    Resumes standard pipeline processing after manual overrides.
    """
    logger.info("applying_manual_override", thread_id=payload.thread_id, action=payload.action)
    config = {"configurable": {"thread_id": payload.thread_id}}

    override_input = {
        "action": payload.action,
        "instructions": payload.instructions
    }

    try:
        # Resume processing dynamically inside existing Graph checkpoints
        state_update = graph_app.invoke(override_input, config=config)
        
        return {
            "thread_id": payload.thread_id,
            "status": state_update.get("session_status"),
            "results": state_update.get("execution_results"),
            "output_artifacts": list(state_update.get("intermediate_artifacts", {}).values())
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Manual resumption failed: {str(err)}")

# ── Modal web service attachment ──
@app.function(secrets=[gcp_secret, llm_secret])
@modal.asgi_app()
def web_service():
    return web_app
```

---

## Running and Demonstrating the Error-Handling Modes

### Setup & Credentials
Create your required access secrets inside your Modal account profile:

```bash
# Register LLM keys (DeepSeek / Tencent)
modal secret create echosapiens-llm-keys LLM_API_KEY="sk-..." LLM_BASE_URL="https://api.lkeap.cloud.tencent.com/v1" LLM_MODEL="deepseek-v4-flash"

# Register GCP service accounts authorized with Storage Object Admin on your target bucket
modal secret create echosapiens-gcp-creds GCP_PROJECT_ID="your_proj_id" GCS_BUCKET_NAME="your_bucket" GOOGLE_APPLICATION_CREDENTIALS="/keys/sa_key.json"
```

Deployment command line execution:
```bash
modal deploy app.py
```

### 1. Verification of `"agentic_self_correction"` Mode
The agent automatically updates parameters and attempts to run and self-correct up to a maximum of 3 times before terminating.

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

### 2. Verification of `"fail_fast_expose"` Mode
Execution terminates immediately on the first non-zero sandbox exit code, and details are returned straight to the caller.

```bash
curl -X POST "https://your-modal-workspace-endpoint.modal.run/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Align genomic reads to hg38 reference databases.",
    "error_handling_preference": "fail_fast_expose",
    "input_artifacts": []
  }'
```

### 3. Verification of `"human_in_the_loop"` Mode
The pipeline is paused, and the state checkpoint is saved.

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