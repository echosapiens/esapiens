"""Budget Service — Grant budget gateway for pre-execution quota checks and spend recording.

Provides:
  - pre_execution_quota_check: Verify remaining grant funds before scheduling a pipeline
  - record_spend: Atomic debit from grant with balance check
  - estimate_pipeline_cost: Cost estimation matrix based on CPU hours, memory, storage
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.grant import Grant
from app.schemas.bio_container import BioContainerStep

logger = logging.getLogger(__name__)


# ── Cost estimation constants ────────────────────────────────────────────

# Pricing model (USD, baseline cloud compute rates)
CPU_HOUR_RATE = Decimal("0.052")        # $0.052 per vCPU-hour
MEMORY_GB_HOUR_RATE = Decimal("0.018")  # $0.018 per GB-hour
STORAGE_GB_RATE = Decimal("0.023")      # $0.023 per GB stored (S3-standard-equivalent)
NETWORK_EGRESS_RATE = Decimal("0.090")  # $0.090 per GB egress

# Default runtime estimates per tool category (hours)
DEFAULT_RUNTIME_ESTIMATES: dict[str, float] = {
    "fastqc": 0.5,
    "bwa-mem2": 2.0,
    "samtools-sort": 1.0,
    "samtools-index": 0.5,
    "gatk4-haplotypecaller": 4.0,
    "gatk4-markduplicates": 1.5,
    "bcftools": 0.5,
    "star-align": 2.0,
    "hisat2": 1.5,
    "picard-markduplicates": 1.0,
    "multiqc": 0.25,
}

# Default storage per step (GB) — conservative estimates
DEFAULT_STORAGE_ESTIMATES: dict[str, Decimal] = {
    "fastqc": Decimal("0.1"),
    "bwa-mem2": Decimal("50.0"),   # large BAM output
    "samtools-sort": Decimal("30.0"),
    "samtools-index": Decimal("0.5"),
    "gatk4-haplotypecaller": Decimal("5.0"),
    "gatk4-markduplicates": Decimal("30.0"),
    "bcftools": Decimal("1.0"),
    "star-align": Decimal("50.0"),
    "hisat2": Decimal("40.0"),
    "picard-markduplicates": Decimal("30.0"),
    "multiqc": Decimal("0.01"),
}

# Overhead multiplier for safety margin (15%)
OVERHEAD_MULTIPLIER = Decimal("1.15")


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class BudgetCheckResult:
    """Result of a pre-execution budget check."""
    has_sufficient_funds: bool
    remaining_budget: Decimal
    estimated_cost: Decimal
    grant_status: str
    grant_id: uuid.UUID | None = None
    shortfall: Decimal = Decimal("0.00")


@dataclass
class SpendRecord:
    """Record of a spend transaction."""
    grant_id: uuid.UUID
    amount: Decimal
    description: str
    previous_spent: Decimal
    new_spent: Decimal
    remaining: Decimal


# ── Service ───────────────────────────────────────────────────────────────

class BudgetService:
    """Grant budget gateway — quota checks, spend recording, and cost estimation."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        """Initialize with an optional database session.

        If no session is provided, a new one will be created for each operation.
        """
        self._external_db = db

    async def _get_db(self) -> AsyncSession:
        """Get a database session — either the injected one or a fresh one."""
        if self._external_db is not None:
            return self._external_db
        return async_session_factory()

    # ── Pre-execution quota check ──────────────────────────────────

    async def pre_execution_quota_check(
        self,
        user_id: uuid.UUID,
        estimated_cost: Decimal,
        grant_id: uuid.UUID | None = None,
    ) -> BudgetCheckResult:
        """Verify remaining grant funds before scheduling a pipeline.

        Args:
            user_id: The user whose grants to check.
            estimated_cost: The estimated cost of the pipeline run.
            grant_id: Optional specific grant to check. If None, checks all
                      active grants for the user and picks the one with the
                      most remaining funds.

        Returns:
            BudgetCheckResult with sufficiency flag and details.
        """
        async with self._get_db() as db:
            # ── Find the grant ────────────────────────────────────
            if grant_id is not None:
                grant = await db.get(Grant, grant_id)
                if grant is None or grant.user_id != user_id:
                    return BudgetCheckResult(
                        has_sufficient_funds=False,
                        remaining_budget=Decimal("0.00"),
                        estimated_cost=estimated_cost,
                        grant_status="not_found",
                        grant_id=grant_id,
                        shortfall=estimated_cost,
                    )
                grants = [grant]
            else:
                # Find all active grants for this user, pick the one with most remaining funds
                stmt = (
                    select(Grant)
                    .where(
                        Grant.user_id == user_id,
                        Grant.status == "active",
                    )
                    .order_by(
                        (Grant.total_budget - Grant.spent_budget).desc()
                    )
                )
                result = await db.execute(stmt)
                grants = list(result.scalars().all())

            if not grants:
                return BudgetCheckResult(
                    has_sufficient_funds=False,
                    remaining_budget=Decimal("0.00"),
                    estimated_cost=estimated_cost,
                    grant_status="no_active_grants",
                    shortfall=estimated_cost,
                )

            # ── Check the best grant ──────────────────────────────
            best_grant = grants[0]
            remaining = best_grant.total_budget - best_grant.spent_budget

            # Apply overhead multiplier to the estimated cost for safety
            adjusted_cost = (estimated_cost * OVERHEAD_MULTIPLIER).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            has_sufficient = remaining >= adjusted_cost
            shortfall = max(Decimal("0.00"), adjusted_cost - remaining)

            return BudgetCheckResult(
                has_sufficient_funds=has_sufficient,
                remaining_budget=remaining,
                estimated_cost=adjusted_cost,
                grant_status=best_grant.status,
                grant_id=best_grant.id,
                shortfall=shortfall,
            )

    # ── Record spend (atomic debit) ────────────────────────────────

    async def record_spend(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        description: str,
        grant_id: uuid.UUID | None = None,
    ) -> SpendRecord:
        """Atomic debit from a grant with balance check.

        Debits the specified amount from the grant's spent_budget within
        an ACID transaction. Raises ValueError if insufficient funds.

        Args:
            user_id: The user whose grant to debit.
            amount: The amount to debit.
            description: Human-readable description of the spend.
            grant_id: Optional specific grant. If None, uses the grant
                      with the most remaining funds.

        Returns:
            SpendRecord with transaction details.

        Raises:
            ValueError: If no active grant found or insufficient funds.
        """
        if amount <= 0:
            raise ValueError(f"Spend amount must be positive, got {amount}")

        # Use a separate session for atomicity if we're managing our own sessions
        manage_session = self._external_db is None
        db = await self._get_db()

        try:
            # ── Find the grant ────────────────────────────────────
            if grant_id is not None:
                grant = await db.get(Grant, grant_id)
                if grant is None:
                    raise ValueError(f"Grant {grant_id} not found")
                if grant.user_id != user_id:
                    raise ValueError(f"Grant {grant_id} does not belong to user {user_id}")
                if grant.status != "active":
                    raise ValueError(f"Grant {grant_id} is not active (status={grant.status})")
            else:
                stmt = (
                    select(Grant)
                    .where(
                        Grant.user_id == user_id,
                        Grant.status == "active",
                    )
                    .order_by(
                        (Grant.total_budget - Grant.spent_budget).desc()
                    )
                    .limit(1)
                    .with_for_update()
                )
                result = await db.execute(stmt)
                grant = result.scalar_one_or_none()
                if grant is None:
                    raise ValueError(f"No active grant found for user {user_id}")

            # ── Check balance ─────────────────────────────────────
            remaining = grant.total_budget - grant.spent_budget
            if remaining < amount:
                raise ValueError(
                    f"Insufficient funds in grant {grant.id}: "
                    f"remaining=${remaining:.2f}, requested=${amount:.2f}"
                )

            # ── Atomic debit ───────────────────────────────────────
            previous_spent = grant.spent_budget
            grant.spent_budget = (grant.spent_budget + amount).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            new_remaining = grant.total_budget - grant.spent_budget

            # ── Check if grant is now exhausted ──────────────────
            if new_remaining <= Decimal("0.01"):
                grant.status = "exhausted"
                logger.info(
                    "Grant %s is now exhausted (remaining=$%s)",
                    grant.id, new_remaining,
                )

            await db.flush()

            record = SpendRecord(
                grant_id=grant.id,
                amount=amount,
                description=description,
                previous_spent=previous_spent,
                new_spent=grant.spent_budget,
                remaining=new_remaining,
            )

            if manage_session:
                await db.commit()

            logger.info(
                "Recorded spend: grant=%s amount=$%s description=%r remaining=$%s",
                grant.id, amount, description, new_remaining,
            )

            return record

        except Exception:
            if manage_session:
                await db.rollback()
            raise

        finally:
            if manage_session:
                await db.close()

    # ── Cost estimation ────────────────────────────────────────────

    @staticmethod
    def estimate_pipeline_cost(steps: list[BioContainerStep]) -> Decimal:
        """Estimate pipeline cost based on CPU hours, memory, and storage.

        Uses a cost estimation matrix with tool-specific runtime and storage
        estimates. Includes a 15% overhead margin.

        Args:
            steps: List of BioContainerStep specifications.

        Returns:
            Estimated total cost in USD as a Decimal.
        """
        total_cost = Decimal("0.00")

        for step in steps:
            # ── Compute cost (CPU + memory) ────────────────────────
            estimated_hours = Decimal(
                str(DEFAULT_RUNTIME_ESTIMATES.get(step.tool_name, 1.0))
            )
            memory_gb = Decimal(str(step.memory_mb)) / Decimal("1024")

            compute_cost = (
                Decimal(str(step.cpus)) * CPU_HOUR_RATE * estimated_hours
                + memory_gb * MEMORY_GB_HOUR_RATE * estimated_hours
            )

            # ── Storage cost ──────────────────────────────────────
            storage_gb = DEFAULT_STORAGE_ESTIMATES.get(
                step.tool_name, Decimal("5.0")
            )
            storage_cost = storage_gb * STORAGE_GB_RATE

            # ── Network cost (if network access needed) ────────────
            network_cost = Decimal("0.00")
            if step.network_access:
                # Estimate 10 GB egress for steps needing network
                network_cost = Decimal("10.0") * NETWORK_EGRESS_RATE

            step_cost = compute_cost + storage_cost + network_cost
            total_cost += step_cost

            logger.debug(
                "Cost estimate for %s: compute=$%s storage=$%s network=$%s total=$%s",
                step.tool_name,
                compute_cost.quantize(Decimal("0.01")),
                storage_cost.quantize(Decimal("0.01")),
                network_cost.quantize(Decimal("0.01")),
                step_cost.quantize(Decimal("0.01")),
            )

        # Apply overhead multiplier
        total_cost = (total_cost * OVERHEAD_MULTIPLIER).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return total_cost

    @staticmethod
    def estimate_step_cost(step: BioContainerStep) -> Decimal:
        """Estimate cost for a single pipeline step.

        Args:
            step: A single BioContainerStep specification.

        Returns:
            Estimated cost in USD as a Decimal.
        """
        return BudgetService.estimate_pipeline_cost([step])