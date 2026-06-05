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
    """Initialize the database and create all tables if they don't exist."""
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
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


def search_jobs(limit: int = 20, status: Optional[str] = None, query: Optional[str] = None) -> list[dict]:
    """Search jobs with optional status filter and text search."""
    conn = _get_connection()
    try:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if query:
            conditions.append("(user_prompt LIKE ? OR id LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Session CRUD ──────────────────────────────────────────────────────────────


def create_session(title: str = "New Chat") -> dict:
    """Create a new session and return it."""
    from datetime import datetime, timezone
    import uuid

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title, now, now),
        )
        conn.commit()
        return {"id": session_id, "title": title, "created_at": now, "updated_at": now}
    finally:
        conn.close()


def list_sessions(limit: int = 20) -> list[dict]:
    """List sessions ordered by updated_at descending."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: str) -> Optional[dict]:
    """Get a single session by ID. Returns None if not found."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: str) -> None:
    """Delete a session and all its messages."""
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


# ── Conversation CRUD ──────────────────────────────────────────────────────────


def add_message(session_id: str, role: str, content: str) -> dict:
    """Add a message to a conversation and update session's updated_at."""
    from datetime import datetime, timezone
    import uuid

    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO conversations (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        conn.commit()
        return {
            "id": msg_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": now,
        }
    finally:
        conn.close()


def get_conversation_history(session_id: str, limit: int = 20) -> list[dict]:
    """Get conversation history ordered by created_at ascending."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()