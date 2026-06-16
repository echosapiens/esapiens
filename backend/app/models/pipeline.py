"""Pipeline ORM model — stores DAG-based bioinformatics pipelines."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # DAG stored as JSONB: list of steps with dependencies
    dag_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────
    session: Mapped["ResearchSession"] = relationship(  # noqa: F821
        "ResearchSession", back_populates="pipelines"
    )
    runs: Mapped[list["Run"]] = relationship(  # noqa: F821
        "Run",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Pipeline id={self.id} name={self.name!r} status={self.status}>"