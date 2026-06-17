"""
state.py — LangGraph State Schemas for State Machine Verification.

Defines the EchoSapiensState TypedDict, reducers for merging complex state
nodes, and structured metadata types for GCS file references, execution
plan steps, and execution results.
"""

import operator
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

# ── Reducers for Merging Complex State Nodes ──


def append_logs(left: list[str], right: list[str]) -> list[str]:
    """Reducer: concatenate log lists without overwriting prior entries."""
    return left + right


def merge_metadata(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer: merge metadata dicts, right takes precedence over left."""
    return {**left, **right}


# ── Structured Metadata Types ──


class GCSFileMetadata(TypedDict):
    """Heavy bioinformatics file metadata reference.

    Stored in state instead of raw file bytes — the orchestrator never
    holds dataset content, only signed URL pointers.
    """

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
    command_template: str  # CLI pattern with {{INPUT_N}}/{{OUTPUT_name}} placeholders
    expected_output_files: list[str]


class ExecutionResult(TypedDict):
    """Execution feedback parsed from the sandbox endpoint."""

    step_id: int
    exit_code: int
    stdout_summary: str
    stderr_summary: str
    uploaded_outputs: list[GCSFileMetadata]
    success: bool


# ── LangGraph State Schema ──


class EchoSapiensState(TypedDict):
    """State machine state representation for bioinformatics pipelines.

    Reducers ensure incremental updates without destroying previous states.
    Heavy data never enters state — only signed URL metadata pointers.
    """

    # Step 1: Hypothesis Formulation (Interactive)
    raw_query: str
    formulated_hypothesis: str | None
    hypothesis_approved: bool
    hypothesis_iterations: int

    # Step 2: Scientific Workflow Planning
    execution_plan: list[PlanStep] | None
    planning_summary: str | None

    # Step 3: Isolated Ephemeral Core Execution
    execution_results: Annotated[list[ExecutionResult], operator.add]
    intermediate_artifacts: Annotated[dict[str, GCSFileMetadata], merge_metadata]

    # Global Execution State
    retry_count: int
    error_handling_preference: Literal[
        "agentic_self_correction",
        "fail_fast_expose",
        "human_in_the_loop",
    ]
    system_errors: Annotated[list[str], append_logs]
    latest_step_in_error: int | None

    # Technical Execution Metadata
    thread_id: str
    session_status: Literal[
        "formulation",
        "planning",
        "running",
        "paused",
        "completed",
        "failed",
    ]

    # Input artifacts passed by the user at pipeline submission
    input_artifacts: list[GCSFileMetadata]
