import type {
  PipelineResponse,
  JobExecution,
  CostEstimate,
} from "@/types";

const API_BASE = "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let message = `API request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new ApiError(message, res.status);
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

export async function submitPipeline(
  prompt: string
): Promise<PipelineResponse> {
  return request<PipelineResponse>("/api/v1/run-pipeline", {
    method: "POST",
    body: JSON.stringify({ user_prompt: prompt }),
  });
}

export async function getJob(jobId: string): Promise<JobExecution> {
  return request<JobExecution>(`/api/v1/jobs/${jobId}`);
}

export async function listJobs(limit?: number): Promise<JobExecution[]> {
  const params = limit ? `?limit=${limit}` : "";
  return request<JobExecution[]>(`/api/v1/jobs${params}`);
}

export async function simulateCost(
  prompt: string,
  tier?: string
): Promise<CostEstimate> {
  return request<CostEstimate>("/api/v1/simulate-cost", {
    method: "POST",
    body: JSON.stringify({ user_prompt: prompt, tier }),
  });
}

export async function deleteJob(jobId: string): Promise<void> {
  return request<void>(`/api/v1/jobs/${jobId}`, {
    method: "DELETE",
  });
}

export function streamPipeline(
  prompt: string,
  onEvent: (event: { type: string; data: any }) => void,
  onError: (error: string) => void,
  onComplete: () => void
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_prompt: prompt }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let message = `Stream request failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (body.detail) message = body.detail;
        } catch {
          // ignore
        }
        onError(message);
        onComplete();
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError("Response body is not readable");
        onComplete();
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events: event: xxx\ndata: {...}\n\n
        const parts = buffer.split("\n\n");
        // Keep the last incomplete chunk in the buffer
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n");
          let eventType = "";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6).trim();
            }
          }

          if (eventType && eventData) {
            try {
              const parsed = JSON.parse(eventData);
              onEvent({ type: eventType, data: parsed });
            } catch {
              onEvent({ type: eventType, data: eventData });
            }
          }
        }
      }

      onComplete();
    } catch (err: unknown) {
      if (controller.signal.aborted) {
        onComplete();
        return;
      }
      const message =
        err instanceof Error ? err.message : "Unknown stream error";
      onError(message);
      onComplete();
    }
  })();

  return controller;
}

export { ApiError };