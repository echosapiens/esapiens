from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class FileRequirement(BaseModel):
    file_type: str  # e.g., 'fastq.gz', 'bam'
    mount_path: str  # e.g., '/data/input/'
    size_bytes: Optional[int] = None
    description: Optional[str] = None


class ContainerContract(BaseModel):
    image_string: str  # quay.io/biocontainers/samtools:1.19--h50ea8bc_0
    exact_cli_command: str  # Tool command (runs in BioContainer)
    download_command: str = ""  # Data download command (runs in Ubuntu sandbox)
    inputs: List[FileRequirement]
    outputs: List[FileRequirement]
    container_timeout_seconds: int = 1200


class JobStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    CONTRACTING = "contracting"
    QUEUED = "queued"
    RUNNING = "running"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


class CostEstimate(BaseModel):
    raw_compute_cost_usd: float
    platform_markup_usd: float
    total_cost_usd: float
    estimated_minutes: int


class JobExecution(BaseModel):
    id: str
    user_prompt: str
    status: JobStatus
    contract: Optional[ContainerContract] = None
    cost_estimate: Optional[CostEstimate] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class PipelineRequest(BaseModel):
    user_prompt: str = "hello"
    data_bucket_url: str = "/data/input/"


class PipelineResponse(BaseModel):
    job_id: str
    status: JobStatus
    contract: Optional[ContainerContract] = None
    cost_estimate: Optional[CostEstimate] = None


class CostSimulationRequest(BaseModel):
    user_prompt: str
    tier: str = "free"