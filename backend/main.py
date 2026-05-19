"""
Main — LangGraph agent orchestration with persistent storage.

Provides run() / run_stream() that use:
  - StorageBackend for session/message persistence (SQLite)
  - SqliteSaver for agent checkpoint persistence (SQLite)

On import: initializes storage, creates the compiled agent graph.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Generator, Optional

import os

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from agent import WorkflowState, agent_graph, build_agent_graph, get_llm
from intent_classifier import classify_query
from storage import StorageBackend, get_storage
from tools import TOOL_DEFINITIONS

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# Secret Hygiene — consume secrets from env, then scrub them
# ═══════════════════════════════════════════════════════════════════════════
# After load_dotenv(), secrets are in os.environ for the process to read.
# We snapshot them into module-level variables so agent.py / tools.py can
# still use them, then DELETE them from os.environ so that execute_python
# (which passes `os` to user code) cannot leak them.

_SECRET_ENV_VARS = [
    "OPENROUTER_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "JWT_SECRET",
]

for _var in _SECRET_ENV_VARS:
    if _var in os.environ:
        # Value is already captured by agent.py / modal_tasks.py at import time
        del os.environ[_var]

# ═══════════════════════════════════════════════════════════════════════════
# Persistent Storage
# ═══════════════════════════════════════════════════════════════════════════

# Initialize storage singleton (creates dirs, DB tables, workspace root)
storage: StorageBackend = get_storage()

# Rebuild agent graph with persistent SQLite checkpointer
# Open a persistent connection for the SqliteSaver (stays open for server lifetime)
_checkpoint_conn = sqlite3.connect(
    str(storage.data_dir / "checkpoints" / "agent_checkpoints.db"),
    check_same_thread=False,
)
_checkpoint_conn.execute("PRAGMA journal_mode=WAL")
_persistent_checkpointer = SqliteSaver(_checkpoint_conn)

# Rebuild graph with persistent checkpointer
agent_graph = build_agent_graph(checkpointer=_persistent_checkpointer)


# ═══════════════════════════════════════════════════════════════════════════
# Session Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _ensure_session(session_id: str, user_id: str = "default") -> dict[str, Any]:
    """Get or create a session, returning the session dict with messages."""
    return storage.get_session(session_id) or storage.ensure_session(session_id, user_id=user_id)


# ═══════════════════════════════════════════════════════════════════════════
# Synchronous Run
# ═══════════════════════════════════════════════════════════════════════════


def run(
    query: str,
    session_id: str = "default",
    config: Optional[dict] = None,
    user_id: str = "default",
) -> dict[str, Any]:
    """Run the agent synchronously on a user query. Persists messages to DB."""
    _ensure_session(session_id, user_id=user_id)
    thread_id = session_id  # Stable thread ID per session

    initial_state: WorkflowState = {
        "messages": [],
        "query": query,
        "result": "",
        "loaded_skills": [],
        "tool_calls": [],
    }

    run_config = {
        "configurable": {"thread_id": thread_id},
        **(config or {}),
    }

    try:
        result_state = agent_graph.invoke(initial_state, run_config)
        response_text = result_state.get("result", "")
        loaded_skills = result_state.get("loaded_skills", [])
        tool_calls = result_state.get("tool_calls", [])

        # Extract visualization from the last tool call result (if any)
        visualization = None
        for tc in tool_calls:
            result_str = tc.get("result", "")
            if result_str:
                try:
                    result_parsed = json.loads(result_str)
                    vis = result_parsed.get("visualization")
                    if vis:
                        visualization = vis
                except (json.JSONDecodeError, TypeError):
                    pass

        # Persist messages to SQLite
        storage.add_message(session_id, "user", query)
        storage.add_message(session_id, "assistant", response_text, skills=loaded_skills, tool_calls=tool_calls, thoughts=[], visualization=visualization)

        return {
            "response": response_text,
            "session_id": session_id,
            "skills": loaded_skills,
            "tool_calls": tool_calls,
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Chat handler error")
        return {
            "response": "An internal error occurred. Please try again.",
            "session_id": session_id,
            "skills": [],
            "tool_calls": [],
            "error": "internal_error",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Streaming Run
# ═══════════════════════════════════════════════════════════════════════════


def run_stream(
    query: str,
    session_id: str = "default",
    user_id: str = "default",
) -> Generator[dict[str, Any], None, None]:
    """
    Run the agent and yield SSE-compatible event dicts.
    Persists messages to SQLite on completion.

    Yields:
      {"event": "thought", ...}
      {"event": "skills_loaded", "data": json_str, ...}
      {"event": "tool_call", ...}
      {"event": "tool_result", ...}
      {"event": "chunk", ...}
      {"event": "visualization", ...}
      {"event": "done", ...}
      {"event": "error", ...}
    """
    _ensure_session(session_id, user_id=user_id)
    thread_id = session_id

    collected_thoughts: list[str] = []

    # Step 1: classify skills
    skill_paths = classify_query(query)
    thought1 = "Classifying intent and loading relevant biological protocols..."
    collected_thoughts.append(thought1)
    yield {"event": "thought", "data": json.dumps({"message": thought1})}
    yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths})}

    # Step 2: build initial state
    initial_state: WorkflowState = {
        "messages": [],
        "query": query,
        "result": "",
        "loaded_skills": [],
        "tool_calls": [],
    }

    run_config = {
        "configurable": {"thread_id": thread_id},
    }

    # Step 3: iterate through graph events
    collected_tool_calls: list[dict[str, Any]] = []
    collected_skills: list[str] = []
    collected_visualization: Optional[dict] = None
    try:
        thought2 = "Allocating neural engine threads for scientific reasoning..."
        collected_thoughts.append(thought2)
        yield {"event": "thought", "data": json.dumps({"message": thought2})}
        for event in agent_graph.stream(initial_state, run_config):
            for event_type, event_data in event.items():
                if "classify_intent" in event_type or event_type == "classify_intent":
                    thought = "Configuring system persona and skill context..."
                    collected_thoughts.append(thought)
                    yield {"event": "thought", "data": json.dumps({"message": thought})}
                elif "call_model" in event_type or event_type == "call_model":
                    thought = "Consulting large language models for trajectory analysis..."
                    collected_thoughts.append(thought)
                    yield {"event": "thought", "data": json.dumps({"message": thought})}
                    node_data = event_data if isinstance(event_data, dict) else {}
                    msgs = node_data.get("messages", [])
                    if msgs:
                        last = msgs[-1]
                        if last.tool_calls:
                            thought = f"Planning {len(last.tool_calls)} computation steps: {', '.join(tc['name'] for tc in last.tool_calls)}"
                            collected_thoughts.append(thought)
                            yield {"event": "thought", "data": json.dumps({"message": thought}) }
                        if hasattr(last, "content") and last.content:
                            yield {
                                "event": "chunk",
                                "data": json.dumps({"content": last.content, "replace": True}),
                            }
                elif "tools_node" in event_type or event_type == "tools_node":
                    thought = "Engaging hardware interface for tool execution..."
                    collected_thoughts.append(thought)
                    yield {"event": "thought", "data": json.dumps({"message": thought})}
                    node_data = event_data if isinstance(event_data, dict) else {}
                    for tc in node_data.get("tool_calls", []):
                        name = tc["name"]
                        collected_tool_calls.append({
                            "name": name,
                            "args": tc.get("args", {}),
                        })
                        thought = f"Executing tool: {name}"
                        collected_thoughts.append(thought)
                        yield {"event": "thought", "data": json.dumps({"message": thought})}
                        yield {
                            "event": "tool_call",
                            "data": json.dumps({"name": tc["name"], "args": tc["args"]}),
                        }
                        result_str = tc.get("result", "")
                        vis_data = None
                        if result_str:
                            try:
                                result_parsed = json.loads(result_str)
                                vis_data = result_parsed.get("visualization") if isinstance(result_parsed, dict) else None
                            except (json.JSONDecodeError, TypeError):
                                pass
                        if vis_data:
                            collected_visualization = vis_data
                            yield {
                                "event": "visualization",
                                "data": json.dumps(vis_data),
                            }
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "id": tc.get("id", ""),
                                "name": tc["name"],
                                "result": result_str,
                                "status": "success",
                            }),
                        }
                elif "finalize" in event_type or event_type == "finalize":
                    thought = "Synthesizing final scientific report..."
                    collected_thoughts.append(thought)
                    yield {"event": "thought", "data": json.dumps({"message": thought})}
                    if isinstance(event_data, dict):
                        collected_skills = event_data.get("loaded_skills", [])
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Stream handler error")
        yield {"event": "error", "data": json.dumps({"message": "An internal error occurred."})}
        return

    # Step 4: get final result
    try:
        final_state = agent_graph.get_state(run_config)
        result_text = ""
        if final_state and final_state.values:
            result_text = final_state.values.get("result", "")

        # Persist to SQLite
        storage.add_message(
            session_id,
            "user",
            query,
            skills=None,
            tool_calls=collected_tool_calls if collected_tool_calls else None,
        )
        storage.add_message(
            session_id,
            "assistant",
            result_text,
            skills=collected_skills,
            tool_calls=collected_tool_calls if collected_tool_calls else None,
            thoughts=collected_thoughts,
            visualization=collected_visualization,
        )

        # Ensure session has a meaningful title from first message
        session = storage.get_session(session_id)
        if session and session.get("message_count", 0) <= 2:
            # Auto-title from first query
            title = query[:60] + ("..." if len(query) > 60 else "")
            storage.update_session_title(session_id, title)

        yield {
            "event": "done",
            "data": json.dumps({"response": result_text, "session_id": session_id}),
        }
    except Exception as e:
        yield {"event": "done", "data": json.dumps({"response": "", "session_id": session_id})}


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


def get_workspace_path(user_id: str, session_id: str) -> Path:
    """Return the workspace directory path for a user's session."""
    return storage.get_workspace_path(user_id, session_id)


def create_user_profile(user_id: str) -> Path:
    """Create a user profile directory with metadata."""
    return storage.create_user_profile(user_id)


def get_data_dir() -> Path:
    """Return the root data directory path."""
    return storage.data_dir