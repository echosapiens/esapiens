"""Workers package."""

from app.workers.outbox_relay import OutboxRelay

__all__ = ["OutboxRelay"]