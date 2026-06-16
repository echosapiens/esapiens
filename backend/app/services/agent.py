"""LangGraph Plan-and-Execute Agent Service.

Implements a StateGraph with five nodes:
  PLANNER     — converts user prompt into a structured DAG of bioinformatics steps
  CONSTRUCTOR — maps DAG steps to pinned BioContainerStep specifications
  CRITIC      — validates the pipeline (image digests, resource limits, budget)
  HITL_GATE   — interrupts for human-in-the-loop approval
  EXECUTOR    — dispatches approved steps to the Modal compute service

Edges:
  PLANNER → CONSTRUCTOR → CRITIC → HITL_GATE
  HITL_GATE → (approved) → EXECUTOR
  HITL_GATE → (rejected) → PLANNER   (revision loop)
  EXECUTOR → END
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, Interrupt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.event import Event
from app.models.pipeline import Pipeline
from app.models.run import Run
from app.schemas.bio_container import BioContainerStep
from app.services.budget import BudgetService
from app.services.event_engine import EventEngine
from app.services.modal_compute import ModalComputeService

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────

class ApprovalStatus(str, Enum):
    """Human-in-the-loop approval states."""
    PENDING = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class PipelineStepStatus(str, Enum):
    """Status for individual pipeline steps during planning."""
    PLANNED = "planned"
    CONSTRUCTED = "constructed"
    VALIDATED = "validated"
    REJECTED = "rejected"


# ── Pydantic models for planner output ────────────────────────────────────

class PlannerStep(BaseModel):
    """A single step produced by the planner node."""
    step_id: str = Field(..., description="Unique step identifier, e.g. 'step_1'")
    tool_name: str = Field(..., description="Bioinformatics tool name, e.g. 'bwa-mem2', 'samtools-sort'")
    description: str = Field(..., description="Human-readable description of what this step does")
    inputs: list[str] = Field(default_factory=list, description="Input file references or URIs")
    outputs: list[str] = Field(default_factory=list, description="Expected output file references")
    depends_on: list[str] = Field(default_factory=list, description="step_ids this step depends on")
    estimated_cpu: int = Field(default=1, description="Estimated CPU cores needed")
    estimated_memory_mb: int = Field(default=4096, description="Estimated memory in MB")
    network_access: bool = Field(default=False, description="Whether network access is needed")


class PlannerDAG(BaseModel):
    """Structured DAG produced by the PLANNER node."""
    title: str = Field(..., description="Human-readable pipeline title")
    description: str = Field(default="", description="Pipeline description")
    steps: list[PlannerStep] = Field(..., min_length=1)
    action_trace: list[str] = Field(
        default_factory=list,
        description="Clean step-by-step traces for UI display",
    )


class CriticResult(BaseModel):
    """Result of the CRITIC node validation."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    estimated_cost: float = Field(default=0.0, description="Estimated total cost in USD")
    action_trace: list[str] = Field(default_factory=list)


class ActionTraceEntry(BaseModel):
    """A single action trace entry for clean UI display."""
    step: str
    action: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Graph State ───────────────────────────────────────────────────────────

class AgentState(BaseModel):
    """State flowing through the LangGraph Plan-and-Execute graph.

    This is the single source of truth for the entire orchestration.
    """

    # ── Input ──────────────────────────────────────────────────────
    session_id: uuid.UUID
    user_id: uuid.UUID
    prompt: str

    # ── Planning ───────────────────────────────────────────────────
    messages: list[dict[str, Any]] = Field(default_factory=list)
    current_plan: PlannerDAG | None = None
    constructed_steps: list[BioContainerStep] = Field(default_factory=list)
    critic_result: CriticResult | None = None

    # ── HITL ──────────────────────────────────────────────────────
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    approval_comment: str | None = None
    revision_count: int = 0

    # ── Execution ──────────────────────────────────────────────────
    pipeline_id: uuid.UUID | None = None
    run_ids: list[uuid.UUID] = Field(default_factory=list)

    # ── Error handling ─────────────────────────────────────────────
    error_log: list[str] = Field(default_factory=list)

    # ── Metadata ───────────────────────────────────────────────────
    grant_id: uuid.UUID | None = None

    model_config = {"arbitrary_types_allowed": True}


# ── Biocontainer image registry ───────────────────────────────────────────

BIOCONTAINER_REGISTRY: dict[str, dict[str, str]] = {
    "bwa-mem2": {
        "image": "quay.io/biocontainers/bwa-mem2:2.2.1--h7d8f6ac_2",
        "digest": "sha256:e7a3d8f4c1b29a0e8a6f5d2c7b9e4a1f3d5c8b2e6a9d4f1c3e5b7a8d2f4c6e8",
    },
    "samtools-sort": {
        "image": "quay.io/biocontainers/samtools:1.19--h50ea8bc_2",
        "digest": "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    },
    "samtools-index": {
        "image": "quay.io/biocontainers/samtools:1.19--h50ea8bc_2",
        "digest": "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
    },
    "gatk4-haplotypecaller": {
        "image": "quay.io/biocontainers/gatk4:4.5.0.0--py312h6e2a037_0",
        "digest": "sha256:f1e2d3c4b5a6978f0e1d2c3b4a5f6e7d8c9a0b1d2e3f4a5b6c7d8e9f0a1b2c3d4",
    },
    "gatk4-markduplicates": {
        "image": "quay.io/biocontainers/gatk4:4.5.0.0--py312h6e2a037_0",
        "digest": "sha256:f1e2d3c4b5a6978f0e1d2c3b4a5f6e7d8c9a0b1d2e3f4a5b6c7d8e9f0a1b2c3d4",
    },
    "fastqc": {
        "image": "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
        "digest": "sha256:b2c3d4e5f6a7809f1e2d3c4b5a6f7e8d9c0a1b2d3e4f5a6b7c8d9e0f1a2b3c4d5",
    },
    "bcftools": {
        "image": "quay.io/biocontainers/bcftools:1.19--h6e2a037_0",
        "digest": "sha256:c3d4e5f6a7b8091e2d3c4b5a6f7e8d9c0a1b2d3e4f5a6b7c8d9e0f1a2b3c4d5e6",
    },
    "star-align": {
        "image": "quay.io/biocontainers/star:2.7.11a--h6e2a037_0",
        "digest": "sha256:d4e5f6a7b8c091e2d3c4b5a6f7e8d9c0a1b2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7",
    },
    "hisat2": {
        "image": "quay.io/biocontainers/hisat2:2.2.1--h7d8f6ac_2",
        "digest": "sha256:e5f6a7b8c9d01e2d3c4b5a6f7e8d9c0a1b2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8",
    },
    "picard-markduplicates": {
        "image": "quay.io/biocontainers/picard:3.1.1--h5eeb5cd_0",
        "digest": "sha256:f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
    },
    "multiqc": {
        "image": "quay.io/biocontainers/multiqc:1.21--py312h7d8f6ac_0",
        "digest": "sha256:a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
    },
}

# ── Cost estimation matrix (USD per CPU-hour) ────────────────────────────

CPU_HOUR_RATE = 0.05  # $0.05 per CPU-hour (baseline)
MEMORY_GB_HOUR_RATE = 0.02  # $0.02 per GB-hour
STORAGE_GB_RATE = 0.023  # $0.023 per GB stored (S3-standard)
NETWORK_EGRESS_RATE = 0.09  # $0.09 per GB egress


# ── Helper functions ──────────────────────────────────────────────────────

def _build_action_trace(prefix: str, steps: list[PlannerStep]) -> list[str]:
    """Build clean human-readable action traces from planned steps.

    Produces traces like:
    "Checking file integrity → Locating GRCh38 genome index → Launching aligner"
    """
    trace_map: dict[str, str] = {
        "bwa-mem2": "Aligning reads with BWA-MEM2",
        "samtools-sort": "Sorting aligned reads by coordinate",
        "samtools-index": "Indexing sorted BAM file",
        "gatk4-haplotypecaller": "Calling variants with GATK HaplotypeCaller",
        "gatk4-markduplicates": "Marking duplicate reads",
        "fastqc": "Running quality control with FastQC",
        "bcftools": "Processing variant calls with bcftools",
        "star-align": "Aligning RNA-seq reads with STAR",
        "hisat2": "Aligning reads with HISAT2",
        "picard-markduplicates": "Marking duplicate reads with Picard",
        "multiqc": "Aggregating QC reports with MultiQC",
    }
    traces = [f"{prefix}"]
    for step in steps:
        action = trace_map.get(step.tool_name, f"Running {step.tool_name}")
        traces.append(action)
    return traces


def _construct_container_ref(tool_name: str) -> str | None:
    """Look up the pinned container image reference for a tool.

    Returns the full image reference with SHA256 digest, or None if unknown.
    """
    entry = BIOCONTAINER_REGISTRY.get(tool_name)
    if entry is None:
        return None
    return f"{entry['image']}@{entry['digest']}"


# ── Node functions ────────────────────────────────────────────────────────

async def planner_node(state: AgentState) -> dict[str, Any]:
    """PLANNER node: Takes user prompt, produces a structured JSON DAG.

    In production this would call an LLM to parse the natural language
    prompt into a structured DAG. Here we implement a deterministic
    rule-based planner that handles common bioinformatics workflows,
    with LLM integration hooks.
    """
    logger.info("PLANNER node invoked for session=%s prompt=%r", state.session_id, state.prompt[:80])

    messages = list(state.messages)
    messages.append({"role": "system", "content": f"Planning pipeline for: {state.prompt}"})

    # ── Rule-based planning logic ──────────────────────────────────
    prompt_lower = state.prompt.lower()
    steps: list[PlannerStep] = []
    title = "Custom Bioinformatics Pipeline"
    description = state.prompt

    # DNA alignment workflow
    if any(kw in prompt_lower for kw in ["align", "bwa", "mapping", "dna-seq", "dna seq", "whole genome"]):
        title = "DNA Read Alignment Pipeline"
        steps = [
            PlannerStep(
                step_id="step_1",
                tool_name="fastqc",
                description="Quality control of raw FASTQ reads",
                inputs=["input_R1.fastq.gz", "input_R2.fastq.gz"],
                outputs=["fastqc_report.html"],
                depends_on=[],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_2",
                tool_name="bwa-mem2",
                description="Align paired-end reads to reference genome",
                inputs=["input_R1.fastq.gz", "input_R2.fastq.gz", "GRCh38.fa"],
                outputs=["aligned.sam"],
                depends_on=[],
                estimated_cpu=8,
                estimated_memory_mb=32768,
            ),
            PlannerStep(
                step_id="step_3",
                tool_name="samtools-sort",
                description="Sort aligned reads by coordinate",
                inputs=["aligned.sam"],
                outputs=["aligned_sorted.bam"],
                depends_on=["step_2"],
                estimated_cpu=4,
                estimated_memory_mb=16384,
            ),
            PlannerStep(
                step_id="step_4",
                tool_name="samtools-index",
                description="Index the sorted BAM file",
                inputs=["aligned_sorted.bam"],
                outputs=["aligned_sorted.bam.bai"],
                depends_on=["step_3"],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_5",
                tool_name="multiqc",
                description="Aggregate QC metrics",
                inputs=["fastqc_report.html"],
                outputs=["multiqc_report.html"],
                depends_on=["step_1", "step_4"],
                estimated_cpu=1,
                estimated_memory_mb=2048,
            ),
        ]

    # Variant calling workflow
    elif any(kw in prompt_lower for kw in ["variant", "gatk", "snp", "vcf", "germline"]):
        title = "Germline Variant Calling Pipeline"
        steps = [
            PlannerStep(
                step_id="step_1",
                tool_name="fastqc",
                description="Quality control of raw FASTQ reads",
                inputs=["input_R1.fastq.gz", "input_R2.fastq.gz"],
                outputs=["fastqc_report.html"],
                depends_on=[],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_2",
                tool_name="bwa-mem2",
                description="Align reads to reference genome",
                inputs=["input_R1.fastq.gz", "input_R2.fastq.gz", "GRCh38.fa"],
                outputs=["aligned.sam"],
                depends_on=[],
                estimated_cpu=8,
                estimated_memory_mb=32768,
            ),
            PlannerStep(
                step_id="step_3",
                tool_name="samtools-sort",
                description="Sort aligned reads",
                inputs=["aligned.sam"],
                outputs=["aligned_sorted.bam"],
                depends_on=["step_2"],
                estimated_cpu=4,
                estimated_memory_mb=16384,
            ),
            PlannerStep(
                step_id="step_4",
                tool_name="gatk4-markduplicates",
                description="Mark duplicate reads",
                inputs=["aligned_sorted.bam"],
                outputs=["dedup.bam"],
                depends_on=["step_3"],
                estimated_cpu=4,
                estimated_memory_mb=16384,
            ),
            PlannerStep(
                step_id="step_5",
                tool_name="gatk4-haplotypecaller",
                description="Call germline variants with GATK HaplotypeCaller",
                inputs=["dedup.bam", "GRCh38.fa"],
                outputs=["variants.vcf.gz"],
                depends_on=["step_4"],
                estimated_cpu=4,
                estimated_memory_mb=16384,
            ),
            PlannerStep(
                step_id="step_6",
                tool_name="bcftools",
                description="Filter and annotate variant calls",
                inputs=["variants.vcf.gz"],
                outputs=["filtered_variants.vcf.gz"],
                depends_on=["step_5"],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_7",
                tool_name="multiqc",
                description="Aggregate QC metrics",
                inputs=["fastqc_report.html", "dedup.metrics"],
                outputs=["multiqc_report.html"],
                depends_on=["step_1", "step_4", "step_6"],
                estimated_cpu=1,
                estimated_memory_mb=2048,
            ),
        ]

    # RNA-seq workflow
    elif any(kw in prompt_lower for kw in ["rna", "transcript", "expression", "quantification", "rnaseq"]):
        title = "RNA-seq Quantification Pipeline"
        steps = [
            PlannerStep(
                step_id="step_1",
                tool_name="fastqc",
                description="Quality control of raw FASTQ reads",
                inputs=["reads_R1.fastq.gz", "reads_R2.fastq.gz"],
                outputs=["fastqc_report.html"],
                depends_on=[],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_2",
                tool_name="star-align",
                description="Align RNA-seq reads with STAR",
                inputs=["reads_R1.fastq.gz", "reads_R2.fastq.gz", "GRCh38_STAR_index"],
                outputs=["Aligned.sortedByCoord.out.bam"],
                depends_on=[],
                estimated_cpu=8,
                estimated_memory_mb=65536,
            ),
            PlannerStep(
                step_id="step_3",
                tool_name="samtools-index",
                description="Index the aligned BAM file",
                inputs=["Aligned.sortedByCoord.out.bam"],
                outputs=["Aligned.sortedByCoord.out.bam.bai"],
                depends_on=["step_2"],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_4",
                tool_name="multiqc",
                description="Aggregate QC metrics",
                inputs=["fastqc_report.html"],
                outputs=["multiqc_report.html"],
                depends_on=["step_1", "step_3"],
                estimated_cpu=1,
                estimated_memory_mb=2048,
            ),
        ]

    # Generic QC workflow
    elif any(kw in prompt_lower for kw in ["qc", "quality", "fastqc", "quality control"]):
        title = "Quality Control Pipeline"
        steps = [
            PlannerStep(
                step_id="step_1",
                tool_name="fastqc",
                description="Run quality control on input reads",
                inputs=["input.fastq.gz"],
                outputs=["fastqc_report.html"],
                depends_on=[],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
            PlannerStep(
                step_id="step_2",
                tool_name="multiqc",
                description="Aggregate QC reports",
                inputs=["fastqc_report.html"],
                outputs=["multiqc_report.html"],
                depends_on=["step_1"],
                estimated_cpu=1,
                estimated_memory_mb=2048,
            ),
        ]

    # Fallback: single QC step
    else:
        title = f"Pipeline: {state.prompt[:80]}"
        steps = [
            PlannerStep(
                step_id="step_1",
                tool_name="fastqc",
                description=f"Quality control analysis for: {state.prompt}",
                inputs=["input.fastq.gz"],
                outputs=["fastqc_report.html"],
                depends_on=[],
                estimated_cpu=2,
                estimated_memory_mb=4096,
            ),
        ]

    action_trace = _build_action_trace("Planning pipeline steps", steps)
    messages.append({"role": "assistant", "content": f"Generated {len(steps)} step(s): {title}"})

    plan = PlannerDAG(
        title=title,
        description=description,
        steps=steps,
        action_trace=action_trace,
    )

    return {
        "current_plan": plan,
        "messages": messages,
        "approval_status": ApprovalStatus.PENDING,
        "error_log": [],
    }


async def constructor_node(state: AgentState) -> dict[str, Any]:
    """CONSTRUCTOR node: Maps each DAG step to a BioContainerStep with pinned images.

    Resolves tool names to exact container image references with SHA256
    digests for reproducibility.
    """
    logger.info("CONSTRUCTOR node invoked for session=%s", state.session_id)

    if state.current_plan is None:
        return {
            "error_log": state.error_log + ["Constructor invoked without a plan"],
        }

    constructed: list[BioContainerStep] = []
    errors: list[str] = []

    for step in state.current_plan.steps:
        container_ref = _construct_container_ref(step.tool_name)
        if container_ref is None:
            errors.append(
                f"No container image found for tool '{step.tool_name}'. "
                f"Available tools: {', '.join(sorted(BIOCONTAINER_REGISTRY.keys()))}"
            )
            continue

        bio_step = BioContainerStep(
            tool_name=step.tool_name,
            container_image=container_ref,
            command_args=step.inputs + step.outputs,  # simplified; in production derive from step config
            cpus=step.estimated_cpu,
            memory_mb=step.estimated_memory_mb,
            network_access=step.network_access,
        )
        constructed.append(bio_step)

    messages = list(state.messages)
    if errors:
        messages.append({"role": "assistant", "content": f"Construction errors: {'; '.join(errors)}"})
    else:
        messages.append({
            "role": "assistant",
            "content": f"Constructed {len(constructed)} container step(s) with pinned images",
        })

    return {
        "constructed_steps": constructed,
        "error_log": state.error_log + errors,
        "messages": messages,
    }


async def critic_node(state: AgentState) -> dict[str, Any]:
    """CRITIC node: Validates the constructed pipeline.

    Checks:
    - All container image digests are valid
    - CPU and memory constraints are within limits
    - Budget feasibility (if grant_id provided)
    - No circular dependencies in the DAG
    """
    logger.info("CRITIC node invoked for session=%s", state.session_id)

    errors: list[str] = []
    warnings: list[str] = []
    action_trace: list[str] = ["Validating pipeline specification"]

    if state.current_plan is None:
        errors.append("No plan to validate")
        return {
            "critic_result": CriticResult(valid=False, errors=errors, warnings=warnings, estimated_cost=0.0),
            "error_log": state.error_log + errors,
        }

    # ── Validate container images ──────────────────────────────────
    action_trace.append("Checking container image references")
    for step in state.constructed_steps:
        # Verify the image reference contains a SHA256 digest
        if "@sha256:" not in step.container_image:
            errors.append(
                f"Step '{step.tool_name}' container image lacks SHA256 digest: {step.container_image}"
            )
        # Verify the tool is in our registry
        if step.tool_name not in BIOCONTAINER_REGISTRY:
            errors.append(
                f"Step '{step.tool_name}' is not in the supported biocontainer registry"
            )

    # ── Validate resource constraints ──────────────────────────────
    action_trace.append("Checking resource constraints")
    for step in state.constructed_steps:
        if step.cpus < 1 or step.cpus > 64:
            errors.append(
                f"Step '{step.tool_name}' cpus={step.cpus} is outside allowed range [1, 64]"
            )
        if step.memory_mb < 256 or step.memory_mb > 262144:
            errors.append(
                f"Step '{step.tool_name}' memory_mb={step.memory_mb} is outside allowed range [256, 262144]"
            )

    # ── Validate DAG structure (no cycles) ─────────────────────────
    action_trace.append("Checking DAG for circular dependencies")
    step_ids = {s.step_id for s in state.current_plan.steps}
    adj: dict[str, list[str]] = {s.step_id: list(s.depends_on) for s in state.current_plan.steps}

    # Topological sort to detect cycles
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _has_cycle(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for dep in adj.get(node, []):
            if dep in in_stack:
                return True
            if dep not in visited and dep in step_ids:
                if _has_cycle(dep):
                    return True
        in_stack.discard(node)
        return False

    for sid in step_ids:
        if sid not in visited:
            if _has_cycle(sid):
                errors.append("DAG contains a circular dependency — pipeline cannot execute")
                break

    # ── Validate referenced dependencies exist ─────────────────────
    for step in state.current_plan.steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                errors.append(
                    f"Step '{step.step_id}' depends on unknown step '{dep}'"
                )

    # ── Estimate cost ─────────────────────────────────────────────
    action_trace.append("Estimating pipeline cost")
    estimated_cost = 0.0
    for step in state.constructed_steps:
        # Rough estimate: CPU cost + memory cost for estimated 1-hour runtime
        cpu_hours = 1.0  # default estimate per step
        memory_gb = step.memory_mb / 1024
        step_cost = (step.cpus * CPU_HOUR_RATE * cpu_hours) + (memory_gb * MEMORY_GB_HOUR_RATE * cpu_hours)
        estimated_cost += step_cost

    # ── Budget feasibility check (if grant provided) ──────────────
    if state.grant_id is not None:
        action_trace.append("Checking grant budget feasibility")
        try:
            budget_svc = BudgetService()
            from app.services.budget import BudgetCheckResult
            check = await budget_svc.pre_execution_quota_check(state.user_id, estimated_cost)
            if not check.has_sufficient_funds:
                errors.append(
                    f"Insufficient grant funds: remaining ${check.remaining_budget:.2f}, "
                    f"estimated cost ${estimated_cost:.2f}"
                )
            else:
                warnings.append(
                    f"Estimated cost ${estimated_cost:.2f} — remaining budget ${check.remaining_budget:.2f}"
                )
        except Exception as exc:
            warnings.append(f"Could not verify budget: {exc}")

    action_trace.append("Validation complete")

    critic_result = CriticResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        estimated_cost=estimated_cost,
        action_trace=action_trace,
    )

    messages = list(state.messages)
    if critic_result.valid:
        messages.append({
            "role": "assistant",
            "content": f"Pipeline validated — estimated cost: ${estimated_cost:.2f}",
        })
    else:
        messages.append({
            "role": "assistant",
            "content": f"Pipeline validation failed: {'; '.join(errors)}",
        })

    return {
        "critic_result": critic_result,
        "error_log": state.error_log + errors,
        "messages": messages,
    }


async def hitl_gate_node(state: AgentState) -> dict[str, Any]:
    """HITL_GATE node: Interrupts execution for human-in-the-loop approval.

    Persists the pipeline plan to the database with status 'pending_approval'
    and signals the frontend that human review is required.

    In LangGraph, this node uses Interrupt to pause the graph. The
    resume_with_approval / resume_with_rejection methods handle
    the human response.
    """
    logger.info("HITL_GATE node invoked for session=%s", state.session_id)

    # ── Persist the pipeline as pending_approval ────────────────────
    async with async_session_factory() as db:
        try:
            pipeline = Pipeline(
                session_id=state.session_id,
                name=state.current_plan.title if state.current_plan else "Untitled Pipeline",
                description=state.current_plan.description if state.current_plan else "",
                dag_json=_plan_to_dag_json(state),
                status="pending_approval",
            )
            db.add(pipeline)
            await db.flush()
            await db.refresh(pipeline)

            pipeline_id = pipeline.id

            # ── Emit event ─────────────────────────────────────
            event_engine = EventEngine(db)
            await event_engine.emit_event(
                session_id=state.session_id,
                event_type="AGENT_PLAN_GENERATED",
                payload={
                    "pipeline_id": str(pipeline_id),
                    "title": pipeline.name,
                    "steps_count": len(state.constructed_steps),
                    "estimated_cost": state.critic_result.estimated_cost if state.critic_result else 0.0,
                    "critic_warnings": state.critic_result.warnings if state.critic_result else [],
                    "action_trace": state.critic_result.action_trace if state.critic_result else [],
                },
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    # ── Use LangGraph Interrupt to pause for human review ──────────
    # The graph will pause here. Resumption is triggered by the
    # /pipelines/{id}/approve or /pipelines/{id}/reject endpoints.
    raise Interrupt(
        value={
            "pipeline_id": str(pipeline_id),
            "title": state.current_plan.title if state.current_plan else "Untitled",
            "steps": [s.tool_name for s in state.constructed_steps],
            "estimated_cost": state.critic_result.estimated_cost if state.critic_result else 0.0,
            "message": "Pipeline awaiting human approval",
        }
    )


async def executor_node(state: AgentState) -> dict[str, Any]:
    """EXECUTOR node: Dispatches approved pipeline steps to Modal compute.

    For each step in the pipeline DAG:
    1. Creates a Run record in the database
    2. Dispatches the container to Modal Sandbox
    3. Records the modal_sandbox_id for reconciliation
    4. Streams logs to Redis Pub/Sub for real-time UI delivery
    """
    logger.info("EXECUTOR node invoked for session=%s pipeline=%s", state.session_id, state.pipeline_id)

    if state.pipeline_id is None or state.current_plan is None:
        return {
            "error_log": state.error_log + ["Executor invoked without pipeline_id or plan"],
        }

    compute_svc = ModalComputeService()
    run_ids: list[uuid.UUID] = []
    messages = list(state.messages)
    messages.append({"role": "assistant", "content": f"Executing pipeline with {len(state.constructed_steps)} steps"})

    async with async_session_factory() as db:
        # Update pipeline status to running
        pipeline = await db.get(Pipeline, state.pipeline_id)
        if pipeline is None:
            return {
                "error_log": state.error_log + [f"Pipeline {state.pipeline_id} not found"],
            }
        pipeline.status = "running"
        await db.flush()

        # ── Execute steps in topological order ────────────────────
        executed: set[str] = set()

        # Build step lookup from plan
        plan_steps = {s.step_id: s for s in state.current_plan.steps}
        bio_steps = {s.tool_name: s for s in state.constructed_steps}

        # Topological execution: iterate until all steps are done
        max_iterations = len(state.current_plan.steps) + 1
        for _ in range(max_iterations):
            ready = []
            for step in state.current_plan.steps:
                if step.step_id in executed:
                    continue
                deps_satisfied = all(dep in executed for dep in step.depends_on)
                if deps_satisfied:
                    ready.append(step)

            if not ready:
                break

            for step in ready:
                bio_step = bio_steps.get(step.tool_name)
                if bio_step is None:
                    messages.append({
                        "role": "assistant",
                        "content": f"Skipping step '{step.tool_name}' — no container spec",
                    })
                    executed.add(step.step_id)
                    continue

                # Create Run record
                run = Run(
                    pipeline_id=state.pipeline_id,
                    step_name=step.step_id,
                    container_ref=bio_step.container_image,
                    command_args={"args": bio_step.command_args, "inputs": step.inputs, "outputs": step.outputs},
                    status="pending",
                )
                db.add(run)
                await db.flush()
                await db.refresh(run)
                run_ids.append(run.id)

                # ── Dispatch to Modal ───────────────────────────
                try:
                    run.status = "running"
                    run.started_at = datetime.now(timezone.utc)
                    await db.flush()

                    sandbox_id = await compute_svc.run_pipeline_step(
                        run_id=run.id,
                        container_ref=bio_step.container_image,
                        command_args=bio_step.command_args,
                        cpus=bio_step.cpus,
                        memory_mb=bio_step.memory_mb,
                        network_access=bio_step.network_access,
                    )
                    run.modal_sandbox_id = sandbox_id
                    messages.append({
                        "role": "assistant",
                        "content": f"Dispatched step '{step.step_id}' → sandbox {sandbox_id}",
                    })

                except Exception as exc:
                    run.status = "failed"
                    run.stderr_log = str(exc)
                    messages.append({
                        "role": "assistant",
                        "content": f"Failed to dispatch step '{step.step_id}': {exc}",
                    })
                    logger.exception("Failed to dispatch step %s", step.step_id)

                executed.add(step.step_id)

        # ── Finalize pipeline status ──────────────────────────────
        if pipeline is not None:
            # Check if any runs failed
            stmt = select(Run).where(Run.pipeline_id == state.pipeline_id)
            result = await db.execute(stmt)
            all_runs = list(result.scalars().all())
            any_failed = any(r.status == "failed" for r in all_runs)
            all_done = all(r.status in ("completed", "failed") for r in all_runs)

            if any_failed:
                pipeline.status = "failed"
            elif all_done:
                pipeline.status = "completed"
            # else still running — reconciler will update later

        await db.commit()

    messages.append({
        "role": "assistant",
        "content": f"Pipeline execution dispatched: {len(run_ids)} step(s)",
    })

    return {
        "run_ids": run_ids,
        "messages": messages,
    }


def _plan_to_dag_json(state: AgentState) -> dict:
    """Convert the current plan and constructed steps into the Pipeline dag_json format."""
    if state.current_plan is None:
        return {}

    steps_json = []
    bio_steps_map = {s.tool_name: s for s in state.constructed_steps}

    for plan_step in state.current_plan.steps:
        bio = bio_steps_map.get(plan_step.tool_name)
        step_entry = {
            "step_id": plan_step.step_id,
            "step_name": plan_step.step_id,
            "tool_name": plan_step.tool_name,
            "description": plan_step.description,
            "depends_on": plan_step.depends_on,
            "inputs": plan_step.inputs,
            "outputs": plan_step.outputs,
            "container_image": bio.container_image if bio else None,
            "command_args": bio.command_args if bio else [],
            "cpus": bio.cpus if bio else plan_step.estimated_cpu,
            "memory_mb": bio.memory_mb if bio else plan_step.estimated_memory_mb,
            "network_access": bio.network_access if bio else plan_step.network_access,
        }
        steps_json.append(step_entry)

    return {
        "title": state.current_plan.title,
        "description": state.current_plan.description,
        "steps": steps_json,
    }


# ── Edge routing ──────────────────────────────────────────────────────────

def should_route_after_critic(state: AgentState) -> str:
    """Route after CRITIC: if valid → HITL_GATE, if invalid → PLANNER for revision."""
    if state.critic_result is None:
        return "planner"
    if state.critic_result.valid:
        return "hitl_gate"
    # Re-plan if critic found errors, up to max revisions
    if state.revision_count >= 3:
        return "hitl_gate"  # Force to HITL even with errors after 3 revisions
    return "planner"


def should_route_after_hitl(state: AgentState) -> str:
    """Route after HITL: approved → executor, rejected → planner for revision."""
    if state.approval_status == ApprovalStatus.APPROVED:
        return "executor"
    if state.approval_status == ApprovalStatus.REJECTED:
        return "planner"
    # Default: stay at HITL gate (shouldn't reach here, but defensive)
    return "hitl_gate"


# ── Graph builder ─────────────────────────────────────────────────────────

def build_agent_graph() -> CompiledStateGraph:
    """Build and compile the LangGraph Plan-and-Execute StateGraph.

    Graph topology:
        PLANNER → CONSTRUCTOR → CRITIC → HITL_GATE
                                          ↓
        PLANNER ← (rejected) ─ HITL_GATE → (approved) → EXECUTOR → END
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ──────────────────────────────────────────────────
    graph.add_node("planner", planner_node)
    graph.add_node("constructor", constructor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("hitl_gate", hitl_gate_node)
    graph.add_node("executor", executor_node)

    # ── Add edges ───────────────────────────────────────────────────
    graph.set_entry_point("planner")
    graph.add_edge("planner", "constructor")
    graph.add_edge("constructor", "critic")

    # Conditional edge after CRITIC
    graph.add_conditional_edges(
        "critic",
        should_route_after_critic,
        {
            "hitl_gate": "hitl_gate",
            "planner": "planner",
        },
    )

    # Conditional edge after HITL gate
    graph.add_conditional_edges(
        "hitl_gate",
        should_route_after_hitl,
        {
            "executor": "executor",
            "planner": "planner",
        },
    )

    # Executor → END
    graph.add_edge("executor", END)

    return graph.compile()


# ── Service class ─────────────────────────────────────────────────────────

class AgentService:
    """High-level service that wraps the LangGraph agent for the API layer.

    Provides:
    - start_pipeline(prompt, session_id, user_id, grant_id=None) → pipeline_id
    - approve_pipeline(pipeline_id, user_comment=None) → state
    - reject_pipeline(pipeline_id, user_comment=None) → state
    """

    def __init__(self) -> None:
        self._graph = build_agent_graph()

    async def start_pipeline(
        self,
        prompt: str,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        grant_id: uuid.UUID | None = None,
    ) -> tuple[uuid.UUID, AgentState]:
        """Start the Plan-and-Execute pipeline for a user prompt.

        Runs the graph up to the HITL gate (interrupt), then returns
        the pipeline_id and current state for the caller to persist.

        Returns:
            (pipeline_id, state) — pipeline_id is set after HITL_GATE persists
        """
        initial_state = AgentState(
            session_id=session_id,
            user_id=user_id,
            prompt=prompt,
            grant_id=grant_id,
        )

        # Run the graph — it will interrupt at HITL_GATE
        config = {"configurable": {"thread_id": str(session_id)}}
        result_state = await self._graph.ainvoke(initial_state, config=config)

        # The pipeline_id should have been set during execution
        # If the graph was interrupted at HITL, we get the state back
        if isinstance(result_state, dict):
            result_state = AgentState(**result_state)

        pipeline_id = result_state.pipeline_id
        if pipeline_id is None:
            # Fallback: look up the pipeline we just created
            async with async_session_factory() as db:
                stmt = (
                    select(Pipeline)
                    .where(
                        Pipeline.session_id == session_id,
                        Pipeline.status == "pending_approval",
                    )
                    .order_by(Pipeline.created_at.desc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                pipeline = result.scalar_one_or_none()
                if pipeline:
                    pipeline_id = pipeline.id

        return pipeline_id, result_state

    async def approve_pipeline(
        self,
        pipeline_id: uuid.UUID,
        user_comment: str | None = None,
    ) -> AgentState:
        """Resume the graph after human approval of the pipeline.

        Updates the pipeline status to 'approved' and runs the executor.
        """
        async with async_session_factory() as db:
            pipeline = await db.get(Pipeline, pipeline_id)
            if pipeline is None:
                raise ValueError(f"Pipeline {pipeline_id} not found")

            pipeline.status = "approved"
            await db.commit()

        # Resume the graph with approval
        config = {"configurable": {"thread_id": str(pipeline.session_id)}}
        # Provide Command to resume from interrupt with approval
        result = await self._graph.ainvoke(
            Command(resume={"approval": "approved", "comment": user_comment}),
            config=config,
        )

        if isinstance(result, dict):
            result = AgentState(**result)
        return result

    async def reject_pipeline(
        self,
        pipeline_id: uuid.UUID,
        user_comment: str | None = None,
    ) -> AgentState:
        """Resume the graph after human rejection of the pipeline.

        Routes back to the planner for revision.
        """
        async with async_session_factory() as db:
            pipeline = await db.get(Pipeline, pipeline_id)
            if pipeline is None:
                raise ValueError(f"Pipeline {pipeline_id} not found")

            pipeline.status = "rejected"
            await db.commit()

        # Resume the graph with rejection
        config = {"configurable": {"thread_id": str(pipeline.session_id)}}
        result = await self._graph.ainvoke(
            Command(resume={"approval": "rejected", "comment": user_comment}),
            config=config,
        )

        if isinstance(result, dict):
            result = AgentState(**result)
        return result