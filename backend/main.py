"""
Main — VPS Orchestrator (Thin Shell)

The VPS handles auth, sessions, storage, and proxies all compute
to the Modal.com service. No agent, no tools, no LLM calls run here.

Architecture:
  Browser → Nginx → VPS FastAPI (auth, sessions, storage)
                        ↓
                    Modal Compute Service (agent, tools, LLM, bio pipelines)
"""

import json
import os
from typing import Any, Generator, Optional

import httpx
from dotenv import load_dotenv

from intent_classifier import classify_query
from agent import classify_tier, QueryTier
from storage import StorageBackend, get_storage

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# Modal Compute URL
# ═══════════════════════════════════════════════════════════════════════════
# The VPS orchestrator proxies all agent execution to this Modal endpoint.
# Set MODAL_COMPUTE_URL in .env or docker-compose.yml.
# Example: https://echosapiens--esapiens-compute-compute-api.modal.run

MODAL_COMPUTE_URL = os.environ.get("MODAL_COMPUTE_URL", "").rstrip("/")
MODAL_TIMEOUT = int(os.environ.get("MODAL_TIMEOUT", "300"))  # 5 min default

# ═══════════════════════════════════════════════════════════════════════════
# Secret Hygiene — scrub secrets from os.environ after reading
# ═══════════════════════════════════════════════════════════════════════════

_SECRET_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "JWT_SECRET",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
]

for _var in _SECRET_ENV_VARS:
    if _var in os.environ:
        del os.environ[_var]

# ═══════════════════════════════════════════════════════════════════════════
# Persistent Storage (VPS-local SQLite)
# ═══════════════════════════════════════════════════════════════════════════

storage: StorageBackend = get_storage()


# ═══════════════════════════════════════════════════════════════════════════
# Session Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _ensure_session(session_id: str, user_id: str = "default") -> dict[str, Any]:
    """Get or create a session, returning the session dict with messages."""
    return storage.get_session(session_id) or storage.ensure_session(session_id, user_id=user_id)


# ═══════════════════════════════════════════════════════════════════════════
# Sync Run — Proxies to Modal /compute/sync
# ═══════════════════════════════════════════════════════════════════════════

def run(
    query: str,
    session_id: str = "default",
    config: Optional[dict] = None,
    user_id: str = "default",
) -> dict[str, Any]:
    """
    Run the agent synchronously via Modal. Persists messages to SQLite.
    """
    _ensure_session(session_id, user_id=user_id)
    skill_paths = classify_query(query)
    tier = classify_tier(query, skill_paths)

    # Persist user message
    storage.add_message(session_id, "user", query)

    if not MODAL_COMPUTE_URL:
        return {
            "response": "⚠️ Modal compute service not configured. Set MODAL_COMPUTE_URL.",
            "session_id": session_id,
            "skills": skill_paths,
            "tool_calls": [],
            "tier": tier.value,
            "error": "modal_not_configured",
        }

    try:
        resp = httpx.post(
            f"{MODAL_COMPUTE_URL}/compute/sync",
            json={
                "query": query,
                "session_id": session_id,
                "skill_paths": skill_paths,
                "user_id": user_id,
            },
            timeout=MODAL_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()

        # Persist assistant message
        storage.add_message(
            session_id,
            "assistant",
            result.get("response", ""),
            skills=result.get("skills"),
            tool_calls=result.get("tool_calls"),
        )

        return {
            "response": result.get("response", ""),
            "session_id": session_id,
            "skills": result.get("skills", []),
            "tool_calls": result.get("tool_calls", []),
            "tier": result.get("tier", tier.value),
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Modal sync compute error")
        return {
            "response": f"⚠️ Compute service error: {str(e)}",
            "session_id": session_id,
            "skills": skill_paths,
            "tool_calls": [],
            "error": "compute_error",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Streaming Run — Proxies SSE from Modal and persists to SQLite
# ═══════════════════════════════════════════════════════════════════════════

def run_stream(
    query: str,
    session_id: str = "default",
    user_id: str = "default",
) -> Generator[dict[str, Any], None, None]:
    """
    Stream agent execution via Modal SSE endpoint.
    Proxies events to the frontend and persists messages to SQLite.

    For DIRECT-tier queries, the VPS can short-circuit and respond
    immediately without calling Modal if the compute URL is not set.
    """
    _ensure_session(session_id, user_id=user_id)
    skill_paths = classify_query(query)
    tier = classify_tier(query, skill_paths)

    # Step 1: Yield initial thought events
    if tier == QueryTier.DIRECT:
        thought1 = "Direct response — skipping agent loop..."
    else:
        thought1 = f"Route: {tier.value} — classifying intent and loading protocols..."
    yield {"event": "thought", "data": json.dumps({"message": thought1})}
    yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths, "tier": tier.value})}

    # Step 2: Persist user message
    user_msg_id = storage.add_message(session_id, "user", query)

    # Step 3: Create empty assistant placeholder
    assistant_msg_id = storage.add_message(
        session_id, "assistant", "",
        skills=skill_paths,
        thoughts=[thought1, "Routing to compute..." if tier != QueryTier.DIRECT else "Fast-path direct response"],
    )

    # Ensure session has a title
    session = storage.get_session(session_id)
    if session and (not session.get("title") or "Session" in session.get("title", "")):
        title = query[:60] + ("..." if len(query) > 60 else "")
        storage.update_session_title(session_id, title)

    # Helper to update assistant message in DB
    collected_thoughts = [thought1, "Routing to compute..." if tier != QueryTier.DIRECT else "Fast-path direct response"]

    def update_assistant(content=None, tool_calls=None, thoughts=None, visualization=None, skills=None):
        try:
            conn = storage.conn
            updates = []
            params = []
            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if tool_calls is not None:
                updates.append("tool_calls = ?")
                params.append(json.dumps(tool_calls))
            if thoughts is not None:
                updates.append("thoughts = ?")
                params.append(json.dumps(thoughts))
            if visualization is not None:
                updates.append("visualization = ?")
                params.append(json.dumps(visualization))
            if skills is not None:
                updates.append("skills = ?")
                params.append(json.dumps(skills))
            if updates:
                sql = f"UPDATE messages SET {', '.join(updates)} WHERE id = ?"
                params.append(assistant_msg_id)
                conn.execute(sql, tuple(params))
                conn.commit()
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except Exception as e:
            print(f"[Persistence] Error updating assistant message: {e}")

    # Step 4: Proxy SSE from Modal
    if not MODAL_COMPUTE_URL:
        yield {"event": "error", "data": json.dumps({"message": "⚠️ Modal compute service not configured. Set MODAL_COMPUTE_URL."})}
        yield {"event": "done", "data": json.dumps({"response": "", "session_id": session_id})}
        return

    collected_tool_calls: list[dict] = []
    collected_skills: list[str] = skill_paths
    collected_visualization: Optional[dict] = None
    result_text = ""

    try:
        with httpx.stream(
            "POST",
            f"{MODAL_COMPUTE_URL}/compute/stream",
            json={
                "query": query,
                "session_id": session_id,
                "skill_paths": skill_paths,
                "user_id": user_id,
            },
            timeout=MODAL_TIMEOUT,
        ) as resp:
            resp.raise_for_status()

            current_event = "message"
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()

                    # Yield event to frontend
                    event_dict = {"event": current_event, "data": data_str}
                    yield event_dict

                    # Accumulate data for persistence
                    try:
                        parsed = json.loads(data_str)
                        if current_event == "thought":
                            msg = parsed.get("message", "")
                            if msg:
                                collected_thoughts.append(msg)
                        elif current_event == "chunk":
                            content = parsed.get("content", "")
                            if content:
                                update_assistant(content=content, thoughts=collected_thoughts)
                        elif current_event == "tool_call":
                            pass  # tool details come in tool_result
                        elif current_event == "tool_result":
                            name = parsed.get("name", "")
                            result_str = parsed.get("result", "")
                            safe_result = result_str
                            if len(safe_result) > 15000:
                                safe_result = safe_result[:15000] + "\n\n[... truncated ...]"
                            collected_tool_calls.append({
                                "id": parsed.get("id", ""),
                                "name": name,
                                "args": {},  # args not in tool_result
                                "result": safe_result,
                                "status": "success",
                            })
                            update_assistant(tool_calls=collected_tool_calls, thoughts=collected_thoughts)
                        elif current_event == "visualization":
                            collected_visualization = parsed
                            update_assistant(visualization=collected_visualization, thoughts=collected_thoughts)
                        elif current_event == "skills_loaded":
                            pass
                        elif current_event == "done":
                            result_text = parsed.get("response", "")
                            collected_skills = parsed.get("skills", collected_skills)
                            collected_tool_calls = parsed.get("tool_calls", collected_tool_calls)
                            collected_visualization = parsed.get("visualization", collected_visualization)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif line == "":
                    current_event = "message"

    except httpx.ConnectError:
        yield {"event": "error", "data": json.dumps({"message": "⚠️ Cannot reach Modal compute service. Check MODAL_COMPUTE_URL."})}
    except httpx.TimeoutException:
        yield {"event": "error", "data": json.dumps({"message": "⚠️ Modal compute service timed out."})}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Modal stream proxy error")
        yield {"event": "error", "data": json.dumps({"message": f"⚠️ Compute service error: {str(e)}"})}

    # Step 5: Persist final assistant message
    update_assistant(
        content=result_text,
        skills=collected_skills,
        tool_calls=collected_tool_calls,
        thoughts=collected_thoughts,
        visualization=collected_visualization,
    )

    yield {"event": "done", "data": json.dumps({"response": result_text, "session_id": session_id})}


# ═══════════════════════════════════════════════════════════════════════════
# Session Management (backed by StorageBackend)
# ═══════════════════════════════════════════════════════════════════════════

def list_sessions(user_id: str = "default") -> list[dict[str, Any]]:
    """Return a list of session summaries for the given user, newest first."""
    return storage.list_sessions(user_id=user_id)


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    """Return full session data (messages included), or None."""
    return storage.get_session(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session and its workspace. Returns True if existed."""
    return storage.delete_session(session_id)


def reset_session(session_id: str) -> dict[str, Any]:
    """Reset a session to empty (keeps the session record)."""
    return storage.reset_session(session_id)


# ═══════════════════════════════════════════════════════════════════════════
# Workspace & User Management
# ═══════════════════════════════════════════════════════════════════════════

def get_workspace_path(user_id: str, session_id: str):
    """Return the workspace directory path for a user's session."""
    from pathlib import Path
    return storage.get_workspace_path(user_id, session_id)


def create_user_profile(user_id: str):
    """Create a user profile directory with metadata."""
    return storage.create_user_profile(user_id)


def get_data_dir():
    """Return the root data directory path."""
    from pathlib import Path
    return storage.get_data_dir()