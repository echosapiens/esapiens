"""Pydantic v2 schema for BioContainer step specification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BioContainerStep(BaseModel):
    """A single bioinformatics tool step — maps to a container invocation.

    Used by the pipeline planner and the DAG executor to run tools in
    isolated containers with pinned SHA256 digests for reproducibility.
    """

    tool_name: str = Field(..., min_length=1, max_length=256)
    container_image: str = Field(
        ...,
        description="Full image reference including pinned SHA256 digest, e.g. quay.io/biocontainers/samtools:1.19--h50ea8bc_2@sha256:abc123...",
    )
    command_args: list[str] = Field(default_factory=list)
    cpus: int = Field(default=1, ge=1, le=64)
    memory_mb: int = Field(default=4096, ge=256, le=262144)
    network_access: bool = Field(default=False)