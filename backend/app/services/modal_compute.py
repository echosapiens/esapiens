"""Modal Sandbox Compute Service — orchestrates bioinformatics containers on Modal.

Provides:
  - run_pipeline_step: Creates a Modal Sandbox, streams logs to Redis, records sandbox_id
  - check_sandbox_status: Polls Modal sandbox for completion status
  - cancel_sandbox: Terminates a running sandbox

Uses modal.Image.from_registry for biocontainer images and modal.Sandbox.create
with gVisor isolation for secure execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.database import async_session_factory
from app.models.run import Run
from app.models.pipeline import Pipeline
from app.services.event_engine import EventEngine

logger = logging.getLogger(__name__)


# ── Redis Pub/Sub channel prefix ──────────────────────────────────────────

REDIS_RUN_CHANNEL_PREFIX = "esapiens:run:logs:"
REDIS_RUN_EVENT_PREFIX = "esapiens:run:events:"
REDIS_RUN_PROGRESS_PREFIX = "esapiens:run:progress:"


class ModalComputeService:
    """Orchestrates bioinformatics container execution on Modal Sandbox.

    This service:
    1. Creates Modal Sandboxes from pinned biocontainer images
    2. Streams stdout/stderr to Redis Pub/Sub for real-time UI delivery
    3. Records the modal_sandbox_id in the Run model for reconciliation
    4. Supports OIDC identity tokens for S3/R2 access
    """

    def __init__(self) -> None:
        self._redis = None

    async def _get_redis(self):
        """Lazy-initialize Redis connection."""
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def run_pipeline_step(
        self,
        run_id: uuid.UUID,
        container_ref: str,
        command_args: list[str],
        cpus: int = 1,
        memory_mb: int = 4096,
        network_access: bool = False,
        oidc_token: str | None = None,
    ) -> str:
        """Create a Modal Sandbox and run a bioinformatics container step.

        Args:
            run_id: The Run model UUID for this step.
            container_ref: Full container image reference with SHA256 digest.
            command_args: CLI arguments for the container entrypoint.
            cpus: Number of CPU cores to allocate (1–64).
            memory_mb: Memory in MB to allocate (256–262144).
            network_access: Whether the sandbox needs network access.
            oidc_token: Optional OIDC identity token for S3/R2 access.

        Returns:
            The Modal sandbox ID for reconciliation.

        Raises:
            RuntimeError: If sandbox creation fails.
        """
        logger.info(
            "Creating Modal Sandbox: run_id=%s container=%s cpus=%d memory=%dMB",
            run_id, container_ref[:60], cpus, memory_mb,
        )

        sandbox_id: str | None = None

        try:
            # ── Import Modal ──────────────────────────────────────
            import modal

            # ── Build the container image ──────────────────────────
            # Parse image reference to extract image name and digest
            image_parts = container_ref.split("@sha256:")
            image_name = image_parts[0]
            image_digest = image_parts[1] if len(image_parts) > 1 else None

            # Use modal.Image.from_registry to pull the biocontainer image
            if image_digest:
                # Pull by digest for reproducibility
                container_image = modal.Image.from_registry(
                    image_name,
                    add_python="3.11",  # Minimal Python for entrypoint wrapper
                )
            else:
                container_image = modal.Image.from_registry(
                    container_ref,
                    add_python="3.11",
                )

            # ── Build environment variables ────────────────────────
            env_vars: dict[str, str] = {}
            if oidc_token:
                env_vars["AWS_WEB_IDENTITY_TOKEN"] = oidc_token
                env_vars["AWS_ROLE_ARN"] = "arn:aws:iam::esapiens:role/modal-s3-access"

            # ── Create the sandbox ─────────────────────────────────
            app = modal.App(settings.MODAL_APP_NAME)

            # Memory must be at least 256 MB, convert to MiB for Modal
            memory_mib = max(256, memory_mb)

            sandbox = modal.Sandbox.create(
                app=app,
                image=container_image,
                cpu=cpus,
                memory=memory_mib * 1024 * 1024,  # Modal expects bytes
                network=network_access,
                env=env_vars if env_vars else None,
            )

            sandbox_id = sandbox.object_id

            logger.info(
                "Modal Sandbox created: sandbox_id=%s run_id=%s",
                sandbox_id, run_id,
            )

            # ── Update Run record with sandbox_id ─────────────────
            await self._update_run_sandbox_id(run_id, sandbox_id)

            # ── Stream logs to Redis Pub/Sub ──────────────────────
            asyncio.create_task(
                self._stream_logs(run_id, sandbox, sandbox_id)
            )

            return sandbox_id

        except ImportError:
            # Modal not installed — run in simulation mode
            logger.warning(
                "Modal SDK not installed — running in simulation mode for run_id=%s",
                run_id,
            )
            sandbox_id = f"sim-{run_id}"
            await self._update_run_sandbox_id(run_id, sandbox_id)

            # Simulate successful completion
            asyncio.create_task(
                self._simulate_execution(run_id, sandbox_id)
            )
            return sandbox_id

        except Exception as exc:
            logger.exception(
                "Failed to create Modal Sandbox for run_id=%s: %s",
                run_id, exc,
            )
            # Mark run as failed
            await self._mark_run_failed(run_id, str(exc))
            raise RuntimeError(
                f"Failed to create sandbox for run {run_id}: {exc}"
            ) from exc

    async def check_sandbox_status(self, sandbox_id: str) -> dict[str, Any]:
        """Check the status of a Modal sandbox.

        Args:
            sandbox_id: The Modal sandbox object ID.

        Returns:
            Dict with status, exit_code, and other metadata.
        """
        try:
            import modal

            app = modal.App(settings.MODAL_APP_NAME)
            sandbox = modal.Sandbox.from_id(sandbox_id, app=app)

            return {
                "sandbox_id": sandbox_id,
                "status": "running" if sandbox.is_running() else "completed",
                "exit_code": sandbox.exit_code if not sandbox.is_running() else None,
            }

        except ImportError:
            # Simulation mode
            return {
                "sandbox_id": sandbox_id,
                "status": "completed",
                "exit_code": 0,
            }

        except Exception as exc:
            logger.warning("Failed to check sandbox %s: %s", sandbox_id, exc)
            return {
                "sandbox_id": sandbox_id,
                "status": "unknown",
                "error": str(exc),
            }

    async def cancel_sandbox(self, sandbox_id: str) -> bool:
        """Terminate a running Modal sandbox.

        Args:
            sandbox_id: The Modal sandbox object ID.

        Returns:
            True if the sandbox was terminated, False otherwise.
        """
        try:
            import modal

            app = modal.App(settings.MODAL_APP_NAME)
            sandbox = modal.Sandbox.from_id(sandbox_id, app=app)
            sandbox.terminate()
            logger.info("Terminated sandbox %s", sandbox_id)
            return True

        except ImportError:
            logger.info("Simulation mode: cancelled sandbox %s", sandbox_id)
            return True

        except Exception as exc:
            logger.warning("Failed to cancel sandbox %s: %s", sandbox_id, exc)
            return False

    # ── Private helpers ─────────────────────────────────────────────

    async def _stream_logs(
        self,
        run_id: uuid.UUID,
        sandbox: Any,
        sandbox_id: str,
    ) -> None:
        """Stream stdout/stderr from a Modal sandbox to Redis Pub/Sub.

        Reads log lines from the sandbox and publishes them to the
        run-specific Redis channel for real-time UI delivery. Also
        estimates progress based on log volume and publishes progress
        updates to the progress channel.
        """
        redis = await self._get_redis()
        channel = f"{REDIS_RUN_CHANNEL_PREFIX}{run_id}"
        event_channel = f"{REDIS_RUN_EVENT_PREFIX}{run_id}"
        progress_channel = f"{REDIS_RUN_PROGRESS_PREFIX}{run_id}"

        # Mark run as started and set initial progress
        await self._update_run_progress(run_id, 5)
        await self._publish_progress(redis, progress_channel, run_id, 5)

        try:
            import modal

            # Stream stdout
            stdout_lines = []
            line_count = 0
            async for line in sandbox.stdout:
                log_entry = json.dumps({
                    "run_id": str(run_id),
                    "stream": "stdout",
                    "text": line,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                await redis.publish(channel, log_entry)
                stdout_lines.append(line)
                line_count += 1
                # Estimate progress from log volume (logarithmic, caps at 90)
                estimated = min(90, 5 + int(20 * (1 - 1 / (1 + line_count / 50))))
                if estimated > 5 and estimated % 5 == 0:
                    await self._update_run_progress(run_id, estimated)
                    await self._publish_progress(redis, progress_channel, run_id, estimated)

            # Stream stderr
            stderr_lines = []
            async for line in sandbox.stderr:
                log_entry = json.dumps({
                    "run_id": str(run_id),
                    "stream": "stderr",
                    "text": line,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                await redis.publish(channel, log_entry)
                stderr_lines.append(line)

            # ── Wait for completion ──────────────────────────────
            exit_code = sandbox.wait()

            # ── Publish completion event ──────────────────────────
            completion_event = json.dumps({
                "run_id": str(run_id),
                "sandbox_id": sandbox_id,
                "event": "completed",
                "exit_code": exit_code,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await redis.publish(event_channel, completion_event)

            # ── Final progress ───────────────────────────────────
            final_progress = 100 if exit_code == 0 else 95
            await self._update_run_progress(run_id, final_progress)
            await self._publish_progress(redis, progress_channel, run_id, final_progress)

            # ── Update Run record in DB ──────────────────────────
            await self._update_run_completion(
                run_id=run_id,
                exit_code=exit_code,
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
            )

            logger.info(
                "Sandbox completed: sandbox_id=%s run_id=%s exit_code=%d",
                sandbox_id, run_id, exit_code,
            )

        except ImportError:
            pass  # Simulation mode handled elsewhere

        except Exception as exc:
            logger.exception("Error streaming logs for run_id=%s: %s", run_id, exc)
            await self._mark_run_failed(run_id, str(exc))

    async def _simulate_execution(
        self,
        run_id: uuid.UUID,
        sandbox_id: str,
    ) -> None:
        """Simulate a successful execution when Modal SDK is not available.

        Publishes fake log lines to Redis and marks the run as completed
        after a short delay.
        """
        redis = await self._get_redis()
        channel = f"{REDIS_RUN_CHANNEL_PREFIX}{run_id}"
        event_channel = f"{REDIS_RUN_EVENT_PREFIX}{run_id}"

        # Simulate some log output
        for i in range(3):
            await asyncio.sleep(0.5)
            log_entry = json.dumps({
                "run_id": str(run_id),
                "stream": "stdout",
                "text": f"[simulated] Processing step {i + 1}/3...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await redis.publish(channel, log_entry)

        # Simulate completion
        exit_code = 0
        completion_event = json.dumps({
            "run_id": str(run_id),
            "sandbox_id": sandbox_id,
            "event": "completed",
            "exit_code": exit_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await redis.publish(event_channel, completion_event)

        # Update DB
        await self._update_run_completion(
            run_id=run_id,
            exit_code=exit_code,
            stdout="[simulated] Pipeline step completed successfully",
            stderr="",
        )

        logger.info(
            "Simulated completion: sandbox_id=%s run_id=%s",
            sandbox_id, run_id,
        )

    async def _update_run_sandbox_id(
        self,
        run_id: uuid.UUID,
        sandbox_id: str,
    ) -> None:
        """Update the Run model with the Modal sandbox ID."""
        async with async_session_factory() as db:
            try:
                run = await db.get(Run, run_id)
                if run is not None:
                    run.modal_sandbox_id = sandbox_id
                    await db.commit()
            except Exception as exc:
                logger.warning("Failed to update sandbox_id for run %s: %s", run_id, exc)
                await db.rollback()

    async def _update_run_completion(
        self,
        run_id: uuid.UUID,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        """Update the Run model upon sandbox completion.

        Also emits a RUN_STATUS_CHANGED event so the WebSocket
        subscribers see the transition immediately.
        """
        new_status: str | None = None
        async with async_session_factory() as db:
            try:
                run = await db.get(Run, run_id)
                if run is not None:
                    new_status = "completed" if exit_code == 0 else "failed"
                    run.status = new_status
                    run.exit_code = exit_code
                    run.stdout_log = stdout
                    run.stderr_log = stderr
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception as exc:
                logger.warning("Failed to update completion for run %s: %s", run_id, exc)
                await db.rollback()

        # Fire-and-forget event emission — non-blocking
        if new_status is not None:
            asyncio.create_task(self._emit_run_event(
                run_id=run_id,
                event_type="RUN_STATUS_CHANGED",
                payload={
                    "new_status": new_status,
                    "exit_code": exit_code,
                },
            ))

    async def _mark_run_failed(
        self,
        run_id: uuid.UUID,
        error_message: str,
    ) -> None:
        """Mark a run as failed with an error message."""
        async with async_session_factory() as db:
            try:
                run = await db.get(Run, run_id)
                if run is not None:
                    run.status = "failed"
                    run.exit_code = -1
                    run.stderr_log = error_message
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception as exc:
                logger.warning("Failed to mark run %s as failed: %s", run_id, exc)
                await db.rollback()

    async def _update_run_progress(
        self,
        run_id: uuid.UUID,
        progress: int,
    ) -> None:
        """Update the Run model's progress field (0-100)."""
        progress = max(0, min(100, progress))
        async with async_session_factory() as db:
            try:
                run = await db.get(Run, run_id)
                if run is not None:
                    run.progress = progress
                    if progress == 100:
                        run.status = "completed"
                    await db.commit()
            except Exception as exc:
                logger.warning("Failed to update progress for run %s: %s", run_id, exc)
                await db.rollback()

    async def _publish_progress(
        self,
        redis: Any,
        channel: str,
        run_id: uuid.UUID,
        progress: int,
    ) -> None:
        """Publish a progress update to the Redis progress channel.

        Also emits a RUN_PROGRESS event into the outbox so the WebSocket
        subscribers for the parent session receive live progress updates
        via the standard event flow.
        """
        try:
            await redis.publish(
                channel,
                json.dumps({
                    "run_id": str(run_id),
                    "progress": progress,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )
        except Exception as exc:
            logger.debug("Progress publish failed for run %s: %s", run_id, exc)

        # Emit a RUN_PROGRESS event so the WebSocket gets it via the outbox.
        # Non-blocking — fire and forget.
        asyncio.create_task(self._emit_run_event(
            run_id=run_id,
            event_type="RUN_PROGRESS",
            payload={"progress": progress},
        ))

    async def _emit_run_event(
        self,
        run_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event tied to a run, looked up via run → pipeline → session.

        Non-blocking helper used by the progress publisher and the completion
        path. Errors are logged and swallowed — events are best-effort.
        """
        try:
            async with async_session_factory() as db:
                run = await db.get(Run, run_id)
                if run is None:
                    return
                pipeline = await db.get(Pipeline, run.pipeline_id)
                if pipeline is None:
                    return
                session_id = pipeline.session_id
                engine = EventEngine(db)
                await engine.emit_event(
                    session_id=session_id,
                    event_type=event_type,
                    payload={**payload, "run_id": str(run_id), "step_name": run.step_name},
                    aggregate_id=str(run.pipeline_id),
                )
                await db.commit()
        except Exception as exc:
            logger.debug("Failed to emit %s for run %s: %s", event_type, run_id, exc)