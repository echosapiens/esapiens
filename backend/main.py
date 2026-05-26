"""
Main — VPS Agent Runtime

The VPS runs the LangGraph agent loop directly, calling OpenRouter for LLM
inference. Heavy bioinformatics tasks (STAR, SRA downloads, DESeq2, etc.) are
dispatched to Modal via pre-built biocontainers from Quay.io/BioContainers.

Architecture:
  Browser -> Nginx -> VPS FastAPI (auth, sessions, storage, agent loop)
                           |
                           +-- OpenRouter (LLM inference -- direct from VPS)
                           |
                           +-- Modal (heavy bio tasks via biocontainers)
"""

import json
import os
from typing import Any, Generator, Optional

from dotenv import load_dotenv

# MUST load .env before agent imports — agent.py reads OPENROUTER_API_KEY
# from os.environ at module level
load_dotenv()

from intent_classifier import classify_query
from agent import classify_tier, QueryTier, direct_llm_response, build_agent_graph
from storage import StorageBackend, get_storage

# ============================================================================
# Secrets stay in environment -- agent.py / tools.py need OPENROUTER_API_KEY
# ============================================================================
# NOTE: tools.py has its own _SECRET_ENV_VARS that masks secrets from
# execute_python's sandbox. We keep them in os.environ for the VPS runtime.

storage: StorageBackend = get_storage()

# Persistent agent graph
agent_graph = build_agent_graph(checkpointer=storage.checkpoint_saver)


# ============================================================================
# Session Helpers
# ============================================================================


def _ensure_session(session_id: str, user_id: str = "default") -> dict[str, Any]:
    """Get or create a session, returning the session dict with messages."""
    return storage.get_session(session_id) or storage.ensure_session(session_id, user_id=user_id)


# ============================================================================
# Sync Run -- Direct agent execution on VPS, no Modal proxy
# ============================================================================


def run(
    query: str,
    session_id: str = "default",
    config: Optional[dict] = None,
    user_id: str = "default",
) -> dict[str, Any]:
    """
    Run the agent synchronously on the VPS, calling OpenRouter directly.
    Persists messages to SQLite.
    """
    _ensure_session(session_id, user_id=user_id)
    skill_paths = classify_query(query)
    tier = classify_tier(query, skill_paths)

    # Persist user message
    storage.add_message(session_id, "user", query)

    if tier == QueryTier.DIRECT:
        response = direct_llm_response(query)
        result = {
            "response": response,
            "session_id": session_id,
            "skills": skill_paths,
            "tool_calls": [],
            "tier": tier.value,
        }
    else:
        try:
            graph_result = agent_graph.invoke(
                {
                    "query": query,
                    "messages": [],
                    "result": "",
                    "loaded_skills": skill_paths,
                    "tool_calls": [],
                },
                config={"configurable": {"thread_id": session_id}},
            )
            response = graph_result.get("result", "")
            tcs = graph_result.get("tool_calls", [])
            result = {
                "response": response,
                "session_id": session_id,
                "skills": graph_result.get("loaded_skills", skill_paths),
                "tool_calls": [
                    {"name": tc["name"], "args": tc.get("args", {}), "result": tc.get("result", "")}
                    for tc in tcs
                ],
                "tier": tier.value,
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Agent sync execution error")
            result = {
                "response": f"\u26a0\ufe0f Agent error: {str(e)}",
                "session_id": session_id,
                "skills": skill_paths,
                "tool_calls": [],
                "error": "agent_error",
            }

    # Persist assistant message
    storage.add_message(
        session_id,
        "assistant",
        result.get("response", ""),
        skills=result.get("skills"),
        tool_calls=result.get("tool_calls"),
    )

    return result


# ============================================================================
# Streaming Run -- SSE events from local agent execution
# ============================================================================


def run_stream(
    query: str,
    session_id: str = "default",
    user_id: str = "default",
) -> Generator[dict[str, Any], None, None]:
    """
    Stream agent execution via SSE, running the LangGraph agent directly on the VPS.
    Calls OpenRouter directly; heavy bio tasks dispatch to Modal via tools.py.

    Event types:
      skills_loaded -- list of matched skill paths + tier
      thought       -- reasoning step
      tool_call     -- tool being invoked
      tool_result   -- tool execution result
      chunk         -- text token from LLM response
      done          -- final response payload
      error         -- error message
    """
    _ensure_session(session_id, user_id=user_id)
    skill_paths = classify_query(query)
    tier = classify_tier(query, skill_paths)

    # Step 1: Initial thoughts
    thought1 = (
        "Direct response -- skipping agent loop..."
        if tier == QueryTier.DIRECT
        else f"Route: {tier.value} -- classifying intent and loading protocols..."
    )
    yield {"event": "thought", "data": json.dumps({"message": thought1})}
    yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths, "tier": tier.value})}

    # Step 2: Persist user message
    storage.add_message(session_id, "user", query)

    # Step 3: Create empty assistant placeholder
    collected_thoughts = [thought1]
    if tier != QueryTier.DIRECT:
        collected_thoughts.append("Executing agent loop on VPS...")

    assistant_msg_id = storage.add_message(
        session_id, "assistant", "",
        skills=skill_paths,
        thoughts=collected_thoughts,
    )

    # Ensure session has a title
    session = storage.get_session(session_id)
    if session and (not session.get("title") or "Session" in session.get("title", "")):
        title = query[:60] + ("..." if len(query) > 60 else "")
        storage.update_session_title(session_id, title)

    # Helper to update assistant message in DB
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

    # Fast path for DIRECT queries
    if tier == QueryTier.DIRECT:
        text = direct_llm_response(query)
        if text:
            for chunk in _chunk_text(text, chunk_size=80):
                yield {"event": "chunk", "data": json.dumps({"content": chunk})}
        update_assistant(content=text)
        yield {
            "event": "done",
            "data": json.dumps({
                "response": text,
                "session_id": session_id,
                "skills": skill_paths,
                "tool_calls": [],
            }),
        }
        return

    # ==========================================================================
    # Agent loop execution -- LangGraph stream on VPS
    # ==========================================================================
    collected_tool_calls: list[dict] = []
    collected_skills: list[str] = skill_paths
    collected_visualization: Optional[dict] = None
    result_text = ""

    try:
        for step in agent_graph.stream({
                "query": query,
                "messages": [],
                "result": "",
                "loaded_skills": skill_paths,
                "tool_calls": [],
            },
            config={"configurable": {"thread_id": session_id}},
        ):
            for node_name, state in step.items():
                if node_name == "call_model":
                    # Check if the AI message requested tools
                    msgs = state.get("messages", [])
                    for msg in msgs:
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                yield {
                                    "event": "tool_call",
                                    "data": json.dumps({
                                        "id": tc.get("id", ""),
                                        "name": tc["name"],
                                        "args": tc.get("args", {}),
                                    }),
                                }
                                collected_thoughts.append(f"Executing {tc['name']}...")
                                update_assistant(thoughts=collected_thoughts)

                elif node_name == "tools_node":
                    tcs = state.get("tool_calls", [])
                    for tc in tcs:
                        safe_result = tc.get("result", "")
                        if len(safe_result) > 15000:
                            safe_result = safe_result[:15000] + "\n\n[... truncated ...]"
                        collected_tool_calls.append({
                            "id": tc.get("id", ""),
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {}),
                            "result": safe_result,
                            "status": "success",
                        })
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "name": tc.get("name", ""),
                                "result": safe_result,
                                "id": tc.get("id", ""),
                            }),
                        }

                        # Extract visualization from tool result JSON
                        raw_result = tc.get("result", "")
                        if raw_result:
                            try:
                                parsed = json.loads(raw_result)
                                if isinstance(parsed, dict) and "visualization" in parsed:
                                    vis_data = parsed["visualization"]
                                    collected_visualization = vis_data
                                    yield {
                                        "event": "visualization",
                                        "data": json.dumps(vis_data),
                                    }
                            except (json.JSONDecodeError, TypeError):
                                pass

                        collected_thoughts.append(f"\u2713 {tc.get('name', '')} completed")
                        update_assistant(tool_calls=collected_tool_calls, thoughts=collected_thoughts)

                elif node_name == "finalize":
                    result_text = state.get("result", "")

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Agent stream execution error")
        yield {"event": "error", "data": json.dumps({"message": f"\u26a0\ufe0f Agent error: {str(e)}"})}
        update_assistant(content=f"Error: {str(e)}", thoughts=collected_thoughts)
        yield {"event": "done", "data": json.dumps({"response": "", "session_id": session_id})}
        return

    # Emit final response as chunks for streaming feel
    if result_text:
        for chunk in _chunk_text(result_text, chunk_size=80):
            yield {"event": "chunk", "data": json.dumps({"content": chunk})}

    # Persist final state
    update_assistant(
        content=result_text,
        skills=collected_skills,
        tool_calls=collected_tool_calls,
        thoughts=collected_thoughts,
        visualization=collected_visualization,
    )

    yield {
        "event": "done",
        "data": json.dumps({
            "response": result_text,
            "session_id": session_id,
            "skills": collected_skills,
            "tool_calls": collected_tool_calls,
            "visualization": collected_visualization,
        }),
    }


def _chunk_text(text: str, chunk_size: int = 80) -> Generator[str, None, None]:
    """Split text into word-boundary chunks for SSE streaming."""
    words = text.split(" ")
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > chunk_size and current:
            yield current.strip() + " "
            current = word + " "
        else:
            current += word + " "
    if current.strip():
        yield current.strip()


# ============================================================================
# Session Management (backed by StorageBackend)
# ============================================================================


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


# ============================================================================
# Workspace & User Management
# ============================================================================


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
