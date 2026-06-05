// TypeScript types matching backend Pydantic models

export interface FileRequirement {
  file_type: string;
  mount_path: string;
  description?: string;
}

export interface ContainerContract {
  image_string: string;
  exact_cli_command: string;
  inputs: FileRequirement[];
  outputs: FileRequirement[];
}

export type JobStatus =
  | "pending"
  | "researching"
  | "contracting"
  | "queued"
  | "running"
  | "streaming"
  | "completed"
  | "failed";

export interface CostEstimate {
  raw_compute_cost_usd: number;
  platform_markup_usd: number;
  total_cost_usd: number;
  estimated_minutes: number;
}

export interface JobExecution {
  id: string;
  user_prompt: string;
  status: JobStatus;
  contract?: ContainerContract;
  cost_estimate?: CostEstimate;
  stdout?: string;
  stderr?: string;
  error?: string;
  created_at: string;
  completed_at?: string;
}

export interface PipelineRequest {
  user_prompt: string;
  data_bucket_url?: string;
}

export interface PipelineResponse {
  job_id: string;
  status: JobStatus;
  contract?: ContainerContract;
  cost_estimate?: CostEstimate;
}