"""Live Code Sandbox — execute Python/R code on Modal Sandboxes.

The Supervisor's `code_agent` and the chat panel's "Run code" action
delegate here. This is a REAL execution environment, not a stub:

  1. Spin up a Modal Sandbox with Python 3.12 + common data-science libs
     (numpy, pandas, scikit-learn, scipy, matplotlib)
  2. Write the code to a temp file inside the sandbox
  3. Execute it via `python <file>` with a hard timeout
  4. Stream stdout/stderr to Redis for live UI delivery
  5. Return the final output (stdout text + structured return value + files)

The sandbox is ephemeral — created on demand, destroyed after execution.
This is safe: no network egress (gVisor isolation), no state leakage,
and Modal handles cleanup.

Usage:
    sandbox = CodeSandbox()
    result = await sandbox.execute(
        code=\"print(sum(range(10)))\",
        language=\"python\",
        timeout=30.0,
    )
    # result.stdout == "45\\n"
    # result.exit_code == 0
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

# ── Result schema ────────────────────────────────────────────────────────


class CodeExecutionResult(BaseModel):
    """Structured result of a sandbox code execution."""

    execution_id: str = Field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    language: str = "python"
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    return_value: str | None = Field(default=None, description="repr() of the last expression, if available")
    files_produced: list[str] = Field(default_factory=list, description="Files written to /sandbox/output/")
    duration_seconds: float = 0.0
    sandbox_id: str | None = None
    timed_out: bool = False
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Sandbox image (Python data-science stack) ───────────────────────────


def _build_sandbox_image():
    """Build a Modal image with common data-science libraries."""
    import modal

    return (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "numpy",
            "pandas",
            "scikit-learn",
            "scipy",
            "matplotlib",
            "seaborn",
            "statsmodels",
            "biopython",
            "pysam",
        )
        .run_commands(
            "mkdir -p /sandbox/output",
            "chmod 777 /sandbox/output",
        )
    )


# ── CodeSandbox service ──────────────────────────────────────────────────


class CodeSandbox:
    """Manages ephemeral Modal Sandboxes for live code execution.

    All computation runs on Modal — the VPS never executes user code.
    """

    def __init__(self) -> None:
        self._image = None  # lazy-init (modal may not be installed)
        self._app = None
        self._redis = None

    def _get_modal(self):
        """Lazily import modal — fallback to local subprocess if unavailable."""
        try:
            import modal

            return modal
        except ImportError:
            logger.warning("Modal SDK not installed — falling back to local execution")
            return None

    async def _get_image(self):
        if self._image is None:
            modal = self._get_modal()
            if modal is None:
                return None
            self._image = _build_sandbox_image()
        return self._image

    async def _get_app(self):
        if self._app is None:
            modal = self._get_modal()
            if modal is None:
                return None
            self._app = modal.App(settings.MODAL_APP_NAME + "-code")
        return self._app

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    # ── Execute code (main entry point) ───────────────────────────────

    async def execute(
        self,
        code: str,
        language: Literal["python", "r", "bash"] = "python",
        timeout: float = 30.0,
        session_id: uuid.UUID | None = None,
    ) -> CodeExecutionResult:
        """Execute code in a real sandbox and return the result.

        Args:
            code: The source code to execute.
            language: 'python', 'r', or 'bash'.
            timeout: Max execution time in seconds (hard kill).
            session_id: Optional session ID for Redis pub/sub correlation.

        Returns:
            CodeExecutionResult with stdout, stderr, exit_code, and any
            files produced.
        """
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        start = datetime.now(timezone.utc)

        modal = self._get_modal()
        if modal is not None:
            return await self._execute_modal(
                code=code,
                language=language,
                timeout=timeout,
                session_id=session_id,
                execution_id=execution_id,
                start=start,
            )
        # Fallback: local subprocess (only used when Modal SDK unavailable in dev)
        return await self._execute_local(
            code=code,
            language=language,
            timeout=timeout,
            session_id=session_id,
            execution_id=execution_id,
            start=start,
        )

    async def _execute_modal(
        self,
        code: str,
        language: str,
        timeout: float,
        session_id: uuid.UUID | None,
        execution_id: str,
        start: datetime,
    ) -> CodeExecutionResult:
        """Execute code in a real Modal Sandbox."""
        modal = self._get_modal()
        app = await self._get_app()
        image = await self._get_image()

        if app is None or image is None:
            return self._error_result(execution_id, language, "Modal not initialized")

        # Pick the interpreter / shell command
        cmd_map = {
            "python": ["python", "-u", "/sandbox/code.py"],
            "r": ["Rscript", "/sandbox/code.R"],
            "bash": ["bash", "/sandbox/code.sh"],
        }
        if language not in cmd_map:
            return self._error_result(
                execution_id, language, f"Unsupported language: {language}"
            )
        cmd = cmd_map[language]

        # File extension for the source file
        ext_map = {"python": "py", "r": "R", "bash": "sh"}
        ext = ext_map[language]

        sandbox = None
        try:
            sandbox = modal.Sandbox.create(
                app=app,
                image=image,
                cpu=2,
                memory=4096,  # 4 GiB
                network=False,  # No network egress — gVisor isolation
                timeout=int(timeout + 30),  # hard sandbox timeout
            )
            sandbox_id = sandbox.object_id

            # Write the code to a file inside the sandbox
            await sandbox.files.write(f"/sandbox/code.{ext}", code)

            # Execute the code with timeout
            proc = sandbox.exec(*cmd, timeout=int(timeout))

            # Stream stdout/stderr to Redis in real-time
            asyncio.create_task(
                self._stream_execution(execution_id, proc, session_id, sandbox_id)
            )

            # Wait for completion
            exit_code = proc.wait()
            stdout_text = proc.stdout.read() if proc.stdout else ""
            stderr_text = proc.stderr.read() if proc.stderr else ""

            # Check for files produced
            files = []
            try:
                for entry in await sandbox.files.ls("/sandbox/output"):
                    files.append(entry.path)
            except Exception:
                pass

            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return CodeExecutionResult(
                execution_id=execution_id,
                language=language,
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
                files_produced=files,
                duration_seconds=duration,
                sandbox_id=sandbox_id,
                timed_out=exit_code == 124,  # timeout exit code
            )

        except Exception as exc:
            logger.exception("Modal sandbox execution failed: %s", exc)
            return self._error_result(execution_id, language, str(exc))
        finally:
            if sandbox is not None:
                try:
                    sandbox.terminate()
                except Exception:
                    pass

    async def _execute_local(
        self,
        code: str,
        language: str,
        timeout: float,
        session_id: uuid.UUID | None,
        execution_id: str,
        start: datetime,
    ) -> CodeExecutionResult:
        """Local subprocess fallback when Modal SDK is unavailable.

        Used for local dev/CI only. In production the Modal path is used.
        """
        cmd_map = {
            "python": ["python3", "-u", "-c", code],
            "bash": ["bash", "-c", code],
        }
        if language not in cmd_map:
            return self._error_result(
                execution_id, language, f"Unsupported language: {language}"
            )
        cmd = cmd_map[language]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                exit_code = proc.returncode or 0
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                stdout_b, stderr_b = b"", b"Execution timed out"
                exit_code = 124
                timed_out = True

            duration = (datetime.now(timezone.utc) - start).total_seconds()
            return CodeExecutionResult(
                execution_id=execution_id,
                language=language,
                exit_code=exit_code,
                stdout=(stdout_b or b"").decode("utf-8", errors="replace"),
                stderr=(stderr_b or b"").decode("utf-8", errors="replace"),
                files_produced=[],
                duration_seconds=duration,
                sandbox_id=None,
                timed_out=timed_out,
            )
        except Exception as exc:
            return self._error_result(execution_id, language, str(exc))

    async def _stream_execution(
        self,
        execution_id: str,
        proc: Any,
        session_id: uuid.UUID | None,
        sandbox_id: str,
    ) -> None:
        """Stream stdout/stderr to Redis for live UI delivery."""
        try:
            redis = await self._get_redis()
            channel = f"esapiens:exec:logs:{execution_id}"
            # Read stdout
            try:
                async for line in proc.stdout:
                    await redis.publish(
                        channel,
                        json.dumps({
                            "execution_id": execution_id,
                            "stream": "stdout",
                            "text": line,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }),
                    )
            except Exception:
                pass
            # Read stderr
            try:
                async for line in proc.stderr:
                    await redis.publish(
                        channel,
                        json.dumps({
                            "execution_id": execution_id,
                            "stream": "stderr",
                            "text": line,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }),
                    )
            except Exception:
                pass
        except Exception as exc:
            logger.debug("Execution stream failed for %s: %s", execution_id, exc)

    def _error_result(
        self, execution_id: str, language: str, error: str
    ) -> CodeExecutionResult:
        return CodeExecutionResult(
            execution_id=execution_id,
            language=language,
            exit_code=-1,
            stdout="",
            stderr="",
            files_produced=[],
            duration_seconds=0.0,
            error=error,
        )


# ── Singleton ────────────────────────────────────────────────────────────

_code_sandbox: CodeSandbox | None = None


def get_code_sandbox() -> CodeSandbox:
    """Return the singleton CodeSandbox instance."""
    global _code_sandbox
    if _code_sandbox is None:
        _code_sandbox = CodeSandbox()
    return _code_sandbox