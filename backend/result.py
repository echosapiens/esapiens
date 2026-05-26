"""
Tool Result Schema — Structured return types for all tool executions.

Why: Python dicts as results have an ambiguity problem — a tool returning
{"result": "no data found"} looks identical to one returning
{"error": "network timeout"} at the call_site. The LLM observes the content
either way and may not correctly interpret the outcome.

ToolResult solves this by enforcing a consistent structure:
  - status: "success" | "error" | "pending" (for background jobs)
  - data:   the result payload (None on error)
  - error:  Error description (None on success)
  - tool:   which tool generated this result
  - meta:   auxiliary info (job_id, timing, file paths)

All tool implementations in tools.py must return a ToolResult.
execute_tool() serializes it to JSON for the LLM's tool_obs node.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional
from enum import Enum


class ToolStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"  # background job, not yet complete


@dataclass
class ToolResult:
    """
    Structured result from any tool call.

    Attributes:
        status:  SUCCESS | ERROR | PENDING
        data:    Result payload (dict, list, str, None). None if status != SUCCESS.
        error:   Error message string. None if status == SUCCESS.
        tool:    Tool name that produced this result.
        job_id:  Optional job ID for background-job tools (run_bio_pipeline, run_modal_job).
        elapsed_ms: Execution time in milliseconds.
        traceback: Full traceback string. Present only when status == ERROR.
    """

    status: ToolStatus
    data: Optional[Any] = None
    error: Optional[str] = None
    tool: Optional[str] = None
    job_id: Optional[str] = None
    elapsed_ms: float = 0.0
    traceback: Optional[str] = None
    visualization: Optional[dict] = None  # Renderable chart/image/structure

    def __post_init__(self):
        # Enforce mutual exclusivity: data only on SUCCESS, error only on ERROR
        if self.status == ToolStatus.SUCCESS and self.error:
            self.error = None
        if self.status == ToolStatus.ERROR and self.data:
            self.data = None

    def to_dict(self) -> dict:
        """Serialize for JSON output to LLM tool_obs node."""
        d: dict[str, Any] = {
            "tool": self.tool or "unknown",
            "status": self.status.value,
        }
        if self.status == ToolStatus.SUCCESS:
            d["data"] = self.data
            if self.visualization:
                d["visualization"] = self.visualization
        elif self.status == ToolStatus.ERROR:
            err_str: str = self.error or "unknown error"
            d["error"] = err_str
            if self.traceback:
                d["traceback"] = self.traceback
        elif self.status == ToolStatus.PENDING:
            jid: str = self.job_id or ""
            d["job_id"] = jid
            d["data"] = self.data
        return d

    @classmethod
    def ok(
        cls,
        tool: str,
        data: Any = None,
        job_id: Optional[str] = None,
        elapsed_ms: float = 0.0,
        visualization: Optional[dict] = None,
    ) -> ToolResult:
        return cls(
            status=ToolStatus.SUCCESS,
            data=data,
            tool=tool,
            job_id=job_id,
            elapsed_ms=elapsed_ms,
            visualization=visualization,
        )

    @classmethod
    def err(
        cls,
        tool: str,
        error: str,
        elapsed_ms: float = 0.0,
        exc_info: Optional[tuple] = None,
    ) -> ToolResult:
        tb_str: Optional[str] = None
        if exc_info is not None:
            import traceback as tb_mod

            tb_str = "".join(tb_mod.format_exception(*exc_info))
        return cls(
            status=ToolStatus.ERROR,
            error=error,
            tool=tool,
            elapsed_ms=elapsed_ms,
            traceback=tb_str,
        )

    @classmethod
    def pending(
        cls,
        tool: str,
        job_id: str,
        data: Any = None,
    ) -> ToolResult:
        return cls(
            status=ToolStatus.PENDING,
            data=data,
            tool=tool,
            job_id=job_id,
        )


# ── Timing helper ─────────────────────────────────────────────────────────────


class _Timer:
    """Context manager for timing a block in milliseconds."""

    def __init__(self):
        self.start: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000


def timed(fn):
    """Decorator: wrap a tool function with automatic elapsed_ms tracking.

    Usage:
        @register_tool("my_tool")
        @timed
        def my_tool(...) -> ToolResult:
            ...
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with _Timer() as t:
            result = fn(*args, **kwargs)
        if isinstance(result, ToolResult):
            result.elapsed_ms = t.elapsed_ms
        elif isinstance(result, dict):
            # Backward compat: wrap plain dicts (should migrate to ToolResult)
            result["elapsed_ms"] = t.elapsed_ms
        return result

    return wrapper
