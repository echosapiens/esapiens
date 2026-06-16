"""User ORM model — the root entity for sessions, grants, and auth."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str | None] = mapped_column(
        String(512), unique=True, nullable=True, index=True
    )
    orcid: Mapped[str | None] = mapped_column(
        String(19), unique=True, nullable=True, index=True
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
    sessions: Mapped[list["ResearchSession"]] = relationship(  # noqa: F821
        "ResearchSession",
        back_populates="user",
        lazy="selectin",
    )
    grants: Mapped[list["Grant"]] = relationship(  # noqa: F821
        "Grant",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"