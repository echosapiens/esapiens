import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "esapiens.db")


def _get_connection() -> sqlite3.Connection:
    """Create a new connection per call (thread-safe pattern)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    """Initialize the database and create the jobs table if it doesn't exist."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_prompt TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                contract_json TEXT,
                cost_json TEXT,
                stdout TEXT,
                stderr TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def create_job(job_id: str, user_prompt: str) -> None:
    """Insert a new job record."""
    from datetime import datetime, timezone

    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO jobs (id, user_prompt, status, created_at) VALUES (?, ?, ?, ?)",
            (job_id, user_prompt, "pending", datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def update_job(job_id: str, **fields) -> None:
    """Update any field(s) on a job record."""
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    conn = _get_connection()
    try:
        conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    """Retrieve a single job by ID. Returns None if not found."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_jobs(limit: int = 20) -> list[dict]:
    """List recent jobs, ordered by creation time descending."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_job(job_id: str) -> None:
    """Delete a job by ID."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
    finally:
        conn.close()