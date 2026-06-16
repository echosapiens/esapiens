"""Run ORM model — individual step executions inside a pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(256), nullable=False)
    container_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    command_args: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", index=True
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modal_sandbox_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    stdout_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────
    pipeline: Mapped["Pipeline"] = relationship(  # noqa: F821
        "Pipeline", back_populates="runs"
    )

    def __repr__(self) -> str:
        return f"<Run id={self.id} step={self.step_name!r} status={self.status}>"