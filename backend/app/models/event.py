"""Event ORM model — append-only event log (event-sourcing)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, ForeignKey, Sequence, Select
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base, async_session_factory

# Global monotonic sequence for event ordering across all sessions.
# PostgreSQL SEQUENCE guarantees uniqueness even under concurrent inserts.
event_seq = Sequence("event_seq", metadata=Base.metadata)

async def next_seq_id(db: AsyncSession) -> int:
    """Generate the next seq_id from the PostgreSQL sequence."""
    result = await db.execute(Select(event_seq.next_value()))
    return result.scalar_one()

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    seq_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────
    session: Mapped["ResearchSession"] = relationship(  # noqa: F821
        "ResearchSession", back_populates="events"
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} type={self.event_type!r}>"