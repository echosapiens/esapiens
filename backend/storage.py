"""
E.sapiens Persistent Storage Layer
══════════════════════════════════════════════════════════════════

Provides:
  1. SQLite-backed session & message store (replaces in-memory _sessions dict)
  2. Per-user, per-session workspace directory management
  3. LangGraph SqliteSaver integration for agent checkpoints

Directory layout:
  /root/persistent/                        ← configurable via ESAPIENS_DATA_DIR
  ├── esapiens.db                          ← Main SQLite database
  ├── checkpoints/                         ← LangGraph checkpoint SQLite files
  │   └── agent_checkpoints.db
  └── workspaces/                          ← Per-user workspace directories
      └── {user_id}/
          ├── .meta.json
          └── sessions/
              └── {session_id}/
                  ├── .meta.json
                  ├── uploads/
                  ├── results/
                  └── logs/
"""

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langgraph.checkpoint.sqlite import SqliteSaver

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

# Schema version for migration tracking
SCHEMA_VERSION = 1

TABLE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    user_id     TEXT NOT NULL DEFAULT 'default',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 0,
    metadata    TEXT NOT NULL DEFAULT '{}'
);
"""

TABLE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL DEFAULT '',
    timestamp   REAL NOT NULL,
    skills      TEXT NOT NULL DEFAULT '[]',
    tool_calls  TEXT NOT NULL DEFAULT '[]',
    thoughts    TEXT NOT NULL DEFAULT '[]',
    visualization TEXT
);
"""

TABLE_META = """
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INDEX_MESSAGES_SESSION = """
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);
"""

INDEX_SESSIONS_USER = """
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at);
"""


# ═══════════════════════════════════════════════════════════════════════════
# StorageBackend
# ═══════════════════════════════════════════════════════════════════════════


class StorageBackend:
    """
    Persistent storage for sessions, messages, and user workspaces.

    Initializes on construction:
      - Creates data directory structure
      - Opens / creates the SQLite database
      - Runs schema migrations
      - Creates workspace root

    Thread-safe for reads. Writes use a single connection with WAL mode
    for concurrency. For production multi-worker setups, consider
    aiosqlite or a connection pool.
    """

    def __init__(self, data_dir: str | Path | None = None):
        self._data_dir = Path(data_dir or os.environ.get(
            "ESAPIENS_DATA_DIR", "./data"
        )).resolve()
        self._db_path = self._data_dir / "esapiens.db"
        self._checkpoints_dir = self._data_dir / "checkpoints"
        self._workspaces_root = self._data_dir / "workspaces"
        self._conn: sqlite3.Connection | None = None
        self._checkpoint_saver: SqliteSaver | None = None

    # ── Initialization ─────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create directories, open DB, run migrations. Call once at startup."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._workspaces_root.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._run_migrations()

    def _run_migrations(self) -> None:
        """Create tables and indexes if they don't exist."""
        assert self._conn is not None
        self._conn.executescript(TABLE_SESSIONS)
        self._conn.executescript(TABLE_MESSAGES)
        self._conn.executescript(TABLE_META)
        self._conn.execute(INDEX_MESSAGES_SESSION)
        self._conn.execute(INDEX_SESSIONS_USER)

        # Migration: Add thoughts column to messages if missing
        try:
            self._conn.execute("ALTER TABLE messages ADD COLUMN thoughts TEXT NOT NULL DEFAULT '[]'")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # Already exists

        # Track schema version
        cur = self._conn.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        )
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO _meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
        self._conn.commit()

    @property
    def checkpoint_saver(self) -> SqliteSaver:
        """
        Return a context-managed SqliteSaver for LangGraph agent checkpoints.

        Usage:
            with storage.checkpoint_saver as saver:
                graph.compile(checkpointer=saver)
        """
        if self._checkpoint_saver is None:
            cp_path = str(self._checkpoints_dir / "agent_checkpoints.db")
            self._checkpoint_saver = SqliteSaver.from_conn_string(cp_path)
        return self._checkpoint_saver

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    @property
    def workspaces_root(self) -> Path:
        return self._workspaces_root

    # ── Connection (for direct queries if needed) ──────────────────────

    @property
    def conn(self) -> sqlite3.Connection:
        assert self._conn is not None, "StorageBackend not initialized"
        return self._conn

    # ── Session CRUD ──────────────────────────────────────────────────

    def ensure_session(self, session_id: str, user_id: str = "default") -> dict[str, Any]:
        """Get or create a session. Returns session dict."""
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = cursor.fetchone()

        if row is not None:
            return dict(row)

        now = time.time()
        self.conn.execute(
            """INSERT INTO sessions (id, title, user_id, created_at, updated_at, message_count, metadata)
               VALUES (?, ?, ?, ?, ?, 0, '{}')""",
            (session_id, f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}", user_id, now, now),
        )
        self.conn.commit()

        # Pre-create workspace directory for this session
        self.ensure_workspace(user_id, session_id)

        return {
            "id": session_id,
            "title": f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
            "metadata": {},
        }

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """Return full session dict with messages, or None."""
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = cursor.fetchone()
        if row is None:
            return None

        session = dict(row)
        session["metadata"] = json.loads(session.get("metadata", "{}"))
        # Convert Unix timestamps to ISO strings for API
        session["created_at"] = datetime.fromtimestamp(session["created_at"], tz=timezone.utc).isoformat()
        session["updated_at"] = datetime.fromtimestamp(session["updated_at"], tz=timezone.utc).isoformat()

        # Load messages
        msg_cursor = self.conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        messages = []
        for msg_row in msg_cursor.fetchall():
            try:
                msg = dict(msg_row)
                # Robust JSON loading for columns that might contain heavy tool data
                for col in ["skills", "tool_calls", "thoughts", "visualization"]:
                    val = msg.get(col)
                    if val:
                        try:
                            msg[col] = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            msg[col] = [] if col != "visualization" else None
                    else:
                        msg[col] = [] if col != "visualization" else None
                
                # Messages timestamp stored as Unix seconds → convert to ms for JS Date
                msg["timestamp"] = int(msg["timestamp"] * 1000)
                messages.append(msg)
            except Exception as e:
                print(f"[Storage] Skipping malformed message: {e}")
                continue

        session["messages"] = messages
        return session

    def list_sessions(self, user_id: str = "default") -> list[dict[str, Any]]:
        """Return summaries of all sessions for a user, newest first."""
        cursor = self.conn.execute(
            """SELECT id, title, user_id, created_at, updated_at, message_count
               FROM sessions WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,),
        )
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            # Convert Unix timestamps → ISO strings for the API
            d["created_at"] = datetime.fromtimestamp(d["created_at"], tz=timezone.utc).isoformat()
            d["updated_at"] = datetime.fromtimestamp(d["updated_at"], tz=timezone.utc).isoformat()
            results.append(d)
        return results

    def update_session_title(self, session_id: str, title: str) -> None:
        self.conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, time.time(), session_id),
        )
        self.conn.commit()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages. Returns True if existed."""
        cursor = self.conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        )
        if cursor.fetchone() is None:
            return False

        self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

        # Remove workspace directory
        self._remove_workspace(session_id)
        return True

    def reset_session(self, session_id: str) -> dict[str, Any]:
        """Clear all messages in a session but keep the session record."""
        self.conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self.conn.execute(
            "UPDATE sessions SET message_count = 0, updated_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        self.conn.commit()
        return self.get_session(session_id) or self.ensure_session(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        skills: Optional[list[str]] = None,
        tool_calls: Optional[list[dict]] = None,
        thoughts: Optional[list[str]] = None,
        visualization: Optional[dict] = None,
    ) -> str:
        """Append a message to a session. Returns message ID."""
        msg_id = f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        now = time.time()

        self.conn.execute(
            """INSERT INTO messages (id, session_id, role, content, timestamp, skills, tool_calls, thoughts, visualization)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                session_id,
                role,
                content or "",
                now,
                json.dumps(skills or []),
                json.dumps(tool_calls or []),
                json.dumps(thoughts or []),
                json.dumps(visualization) if visualization else None,
            ),
        )

        # Update session message count and timestamp
        count_cursor = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
            (session_id,),
        )
        count = count_cursor.fetchone()["cnt"]

        self.conn.execute(
            "UPDATE sessions SET message_count = ?, updated_at = ? WHERE id = ?",
            (count, now, session_id),
        )
        self.conn.commit()

        return msg_id

    def update_last_assistant_content(self, session_id: str, chunk: str) -> None:
        """
        Append content to the last assistant message in a session.
        Used during streaming to update the message incrementally.
        """
        cursor = self.conn.execute(
            """SELECT id, content FROM messages
               WHERE session_id = ? AND role = 'assistant'
               ORDER BY timestamp DESC LIMIT 1""",
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return

        msg_id = row["id"]
        existing = row["content"] or ""
        self.conn.execute(
            "UPDATE messages SET content = ? WHERE id = ?",
            (existing + chunk, msg_id),
        )
        self.conn.commit()

    # ── Workspace Management ──────────────────────────────────────────

    def ensure_workspace(self, user_id: str, session_id: str) -> Path:
        """Create workspace directory for a user's session. Returns path."""
        path = self._workspaces_root / user_id / "sessions" / session_id
        path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (path / "uploads").mkdir(exist_ok=True)
        (path / "results").mkdir(exist_ok=True)
        (path / "logs").mkdir(exist_ok=True)

        # Write meta file if not exists
        meta_path = path / ".meta.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps({
                "user_id": user_id,
                "session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2))

        return path

    def get_workspace_path(self, user_id: str, session_id: str) -> Path:
        """Return workspace path for a session (does not create)."""
        return self._workspaces_root / user_id / "sessions" / session_id

    def _remove_workspace(self, session_id: str) -> None:
        """Remove workspace directory for a session (best-effort)."""
        import shutil
        # Search across all users for this session
        if not self._workspaces_root.exists():
            return
        for user_dir in self._workspaces_root.iterdir():
            if not user_dir.is_dir():
                continue
            session_dir = user_dir / "sessions" / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir, ignore_errors=True)

    def create_user_profile(self, user_id: str) -> Path:
        """Create a user profile directory. Returns path to profile."""
        user_dir = self._workspaces_root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        meta_path = user_dir / ".meta.json"
        if not meta_path.exists():
            meta_path.write_text(json.dumps({
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2))

        return user_dir

    # ── Cleanup ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════════════
# Global singleton
# ═══════════════════════════════════════════════════════════════════════════

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the global StorageBackend singleton, initializing if needed."""
    global _storage
    if _storage is None:
        _storage = StorageBackend()
        _storage.initialize()
    return _storage


def reset_storage() -> None:
    """Reset the storage singleton (for testing)."""
    global _storage
    if _storage is not None:
        _storage.close()
        _storage = None