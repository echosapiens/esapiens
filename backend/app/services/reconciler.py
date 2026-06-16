"""Job Status Reconciler — polls Modal sandbox states and updates Run models.

Provides:
  - reconcile_run: Poll a single run's Modal sandbox status, update if changed
  - reconcile_all_active: Iterate all running runs, reconcile their Modal states
  - start_background_reconciler: Run reconciliation on a configurable interval

This reconciler ensures that the database state stays in sync with the
actual compute state in Modal, even if event delivery is delayed or
interrupted.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.pipeline import Pipeline
from app.models.run import Run
from app.services.event_engine import EventEngine
from app.services.modal_compute import ModalComputeService

logger = logging.getLogger(__name__)


# ── Reconciliation state tracking ─────────────────────────────────────────

class ReconciliationResult:
    """Result of a single run reconciliation."""

    def __init__(
        self,
        run_id: uuid.UUID,
        previous_status: str,
        new_status: str,
        exit_code: int | None = None,
        sandbox_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.previous_status = previous_status
        self.new_status = new_status
        self.exit_code = exit_code
        self.sandbox_id = sandbox_id
        self.error = error
        self.changed = previous_status != new_status

    def __repr__(self) -> str:
        changed_str = "CHANGED" if self.changed else "unchanged"
        return (
            f"<ReconciliationResult run={self.run_id} "
            f"{self.previous_status}→{self.new_status} {changed_str}>"
        )


class Reconciler:
    """Job status reconciler that keeps Run models in sync with Modal sandboxes.

    Usage:
        reconciler = Reconciler()
        result = await reconciler.reconcile_run(run_id)
        # or
        results = await reconciler.reconcile_all_active()

        # Background task:
        await reconciler.start_background_reconciler(interval_seconds=30)
    """

    def __init__(
        self,
        compute_service: ModalComputeService | None = None,
        reconcile_interval_seconds: int = 30,
    ) -> None:
        self._compute = compute_service or ModalComputeService()
        self._running = False
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._interval = reconcile_interval_seconds

    # ── Single run reconciliation ───────────────────────────────────

    async def reconcile_run(self, run_id: uuid.UUID) -> ReconciliationResult:
        """Poll Modal sandbox status for a single run and update if state changed.

        Args:
            run_id: The Run model UUID to reconcile.

        Returns:
            ReconciliationResult with before/after status.
        """
        async with async_session_factory() as db:
            try:
                run = await db.get(Run, run_id)
                if run is None:
                    return ReconciliationResult(
                        run_id=run_id,
                        previous_status="unknown",
                        new_status="unknown",
                        error=f"Run {run_id} not found",
                    )

                previous_status = run.status

                # ── Only reconcile pending/running runs ────────────
                if run.status not in ("pending", "running"):
                    return ReconciliationResult(
                        run_id=run_id,
                        previous_status=run.status,
                        new_status=run.status,
                        sandbox_id=run.modal_sandbox_id,
                    )

                # ── If no sandbox_id yet, check if it's still pending dispatch
                if run.modal_sandbox_id is None:
                    # Check if the run has been pending too long (stale)
                    if run.started_at is not None:
                        age = (datetime.now(timezone.utc) - run.started_at).total_seconds()
                        if age > settings.MODAL_TIMEOUT:
                            logger.warning(
                                "Run %s has been pending for %ds without sandbox_id — marking failed",
                                run_id, int(age),
                            )
                            run.status = "failed"
                            run.exit_code = -1
                            run.stderr_log = (
                                f"Run timed out after {int(age)}s without being dispatched to Modal"
                            )
                            run.completed_at = datetime.now(timezone.utc)
                            await db.commit()

                            # Emit event
                            event_engine = EventEngine(db)
                            await event_engine.emit_event(
                                session_id=run.pipeline.session_id,  # type: ignore
                                event_type="RUN_FAILED",
                                payload={
                                    "run_id": str(run_id),
                                    "step_name": run.step_name,
                                    "error": "Timed out without sandbox dispatch",
                                },
                            )

                            return ReconciliationResult(
                                run_id=run_id,
                                previous_status=previous_status,
                                new_status="failed",
                                exit_code=-1,
                            )

                    # Still pending dispatch
                    return ReconciliationResult(
                        run_id=run_id,
                        previous_status=run.status,
                        new_status=run.status,
                    )

                # ── Poll Modal for sandbox status ─────────────────
                sandbox_status = await self._compute.check_sandbox_status(
                    run.modal_sandbox_id
                )

                modal_status = sandbox_status.get("status", "unknown")
                modal_exit_code = sandbox_status.get("exit_code")

                # ── Map Modal status to Run status ─────────────────
                new_status = run.status  # default: unchanged
                exit_code = run.exit_code

                if modal_status == "completed":
                    new_status = "completed" if modal_exit_code == 0 else "failed"
                    exit_code = modal_exit_code
                elif modal_status == "running":
                    new_status = "running"
                elif modal_status == "unknown":
                    # Could not reach Modal — leave status unchanged but log
                    logger.warning(
                        "Could not determine Modal status for sandbox %s (run %s)",
                        run.modal_sandbox_id, run_id,
                    )

                # ── Update if changed ─────────────────────────────
                if new_status != previous_status:
                    run.status = new_status
                    if exit_code is not None:
                        run.exit_code = exit_code
                    if new_status in ("completed", "failed"):
                        run.completed_at = datetime.now(timezone.utc)

                    await db.commit()

                    # ── Emit state change event ────────────────────
                    event_type_map = {
                        "running": "RUN_STARTED",
                        "completed": "RUN_COMPLETED",
                        "failed": "RUN_FAILED",
                    }
                    event_type = event_type_map.get(new_status, "RUN_LOG")

                    event_engine = EventEngine(db)
                    await event_engine.emit_event(
                        session_id=run.pipeline.session_id,  # type: ignore
                        event_type=event_type,
                        payload={
                            "run_id": str(run_id),
                            "step_name": run.step_name,
                            "previous_status": previous_status,
                            "new_status": new_status,
                            "exit_code": exit_code,
                        },
                        aggregate_id=str(run.pipeline_id),
                    )

                    logger.info(
                        "Reconciled run %s: %s → %s",
                        run_id, previous_status, new_status,
                    )

                    # ── Also check if parent pipeline should update ─
                    await self._reconcile_pipeline_status(db, run.pipeline_id)

                return ReconciliationResult(
                    run_id=run_id,
                    previous_status=previous_status,
                    new_status=new_status,
                    exit_code=exit_code,
                    sandbox_id=run.modal_sandbox_id,
                )

            except Exception as exc:
                logger.exception("Error reconciling run %s: %s", run_id, exc)
                return ReconciliationResult(
                    run_id=run_id,
                    previous_status="unknown",
                    new_status="unknown",
                    error=str(exc),
                )

    # ── Batch reconciliation ─────────────────────────────────────────

    async def reconcile_all_active(self) -> list[ReconciliationResult]:
        """Reconcile all active (pending/running) runs.

        Iterates through all runs with status 'pending' or 'running',
        polls their Modal sandbox states, and updates the database.

        Returns:
            List of ReconciliationResult for each active run.
        """
        results: list[ReconciliationResult] = []

        async with async_session_factory() as db:
            stmt = (
                select(Run)
                .where(Run.status.in_(["pending", "running"]))
                .order_by(Run.created_at.asc())
            )
            result = await db.execute(stmt)
            active_runs = list(result.scalars().all())

        logger.info("Reconciling %d active runs", len(active_runs))

        for run in active_runs:
            try:
                reconciliation = await self.reconcile_run(run.id)
                results.append(reconciliation)
            except Exception as exc:
                logger.exception("Failed to reconcile run %s: %s", run.id, exc)
                results.append(ReconciliationResult(
                    run_id=run.id,
                    previous_status=run.status,
                    new_status=run.status,
                    error=str(exc),
                ))

            # Small delay between reconciliations to avoid rate limiting
            await asyncio.sleep(0.1)

        changed = sum(1 for r in results if r.changed)
        logger.info(
            "Reconciliation complete: %d runs checked, %d status changes",
            len(results), changed,
        )

        return results

    # ── Pipeline status reconciliation ──────────────────────────────

    async def _reconcile_pipeline_status(
        self,
        db: AsyncSession,
        pipeline_id: uuid.UUID,
    ) -> str | None:
        """Check if a pipeline's status should be updated based on its runs.

        Transition rules:
        - If all runs are completed → pipeline status = "completed"
        - If any run is failed and all others are completed/failed → pipeline status = "failed"
        - If any run is running → pipeline status = "running"
        - If all runs are pending → pipeline status = "submitted"

        Returns:
            The new pipeline status, or None if unchanged.
        """
        pipeline = await db.get(Pipeline, pipeline_id)
        if pipeline is None:
            return None

        stmt = select(Run).where(Run.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        runs = list(result.scalars().all())

        if not runs:
            return None

        statuses = {r.status for r in runs}
        new_status: str | None = None

        if all(s == "completed" for s in statuses):
            new_status = "completed"
        elif "running" in statuses:
            new_status = "running"
        elif "failed" in statuses and all(s in ("completed", "failed") for s in statuses):
            new_status = "failed"
        elif all(s == "pending" for s in statuses):
            new_status = "submitted"
        elif "pending" in statuses and "completed" in statuses:
            # Some steps completed, others pending — still in progress
            new_status = "running"

        if new_status and new_status != pipeline.status:
            old_status = pipeline.status
            pipeline.status = new_status
            await db.flush()

            # Emit event
            event_engine = EventEngine(db)
            await event_engine.emit_event(
                session_id=pipeline.session_id,
                event_type="PIPELINE_STATUS_CHANGED",
                payload={
                    "pipeline_id": str(pipeline_id),
                    "old_status": old_status,
                    "new_status": new_status,
                },
                aggregate_id=str(pipeline_id),
            )

            logger.info(
                "Pipeline %s status: %s → %s",
                pipeline_id, old_status, new_status,
            )
            return new_status

        return None

    # ── Background task ──────────────────────────────────────────────

    async def start_background_reconciler(self, interval_seconds: int | None = None) -> None:
        """Start the reconciler as a background asyncio task.

        Args:
            interval_seconds: Override the reconciliation interval.
                            Defaults to the value set at construction time.
        """
        if self._running:
            logger.warning("Reconciler is already running")
            return

        self._interval = interval_seconds or self._interval
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Background reconciler started (interval=%ds)", self._interval)

    async def stop_background_reconciler(self) -> None:
        """Stop the background reconciler task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Background reconciler stopped")

    async def _run_loop(self) -> None:
        """Main reconciliation loop that runs periodically."""
        while self._running:
            try:
                await self.reconcile_all_active()
            except Exception:
                logger.exception("Error during reconciliation cycle")
            await asyncio.sleep(self._interval)

    # ── Status summary ──────────────────────────────────────────────

    async def get_status_summary(self) -> dict[str, Any]:
        """Get a summary of active run counts and reconciliation state.

        Returns:
            Dict with counts of pending, running, completed, and failed runs.
        """
        async with async_session_factory() as db:
            from sqlalchemy import func

            # Count runs by status
            stmt = select(Run.status, func.count(Run.id)).group_by(Run.status)
            result = await db.execute(stmt)
            status_counts = dict(result.all())

            # Count active pipelines
            active_pipelines_stmt = select(func.count(Pipeline.id)).where(
                Pipeline.status.in_(["submitted", "running", "pending_approval"])
            )
            active_result = await db.execute(active_pipelines_stmt)
            active_pipelines = active_result.scalar_one()

            return {
                "run_counts": {
                    "pending": status_counts.get("pending", 0),
                    "running": status_counts.get("running", 0),
                    "completed": status_counts.get("completed", 0),
                    "failed": status_counts.get("failed", 0),
                },
                "active_pipelines": active_pipelines,
                "reconciler_running": self._running,
                "reconciler_interval_seconds": self._interval,
            }