"""
Modal Compute Service — Optional standalone agent deployment (DEPRECATED primary path)

ARCHITECTURE CHANGE (May 2026):
  The VPS now runs the LangGraph agent loop directly, calling OpenRouter locally.
  Heavy bio tasks are dispatched to Modal via modal_tasks.py (biocontainers from
  Quay.io). This file is retained as an optional deployment for running the agent
  on Modal instead of the VPS (e.g., for isolated testing or failover).

  To use this instead of the local agent on VPS:
    modal deploy backend/modal_compute.py
    export MODAL_COMPUTE_URL=<deployed-url>

The deployed URL becomes MODAL_COMPUTE_URL in the VPS .env (optional override).
"""
Deploy:
    modal secret create esapiens-secrets OPENROUTER_API_KEY=sk-or-v1-... BRAVE_SEARCH_API_KEY=BSA...
    modal deploy backend/modal_compute.py

The deployed URL becomes MODAL_COMPUTE_URL in the VPS .env.
"""

import modal
import json
import sqlite3
import os
from typing import Any, Generator, Optional

# ═══════════════════════════════════════════════════════════════════════════
# Modal App & Image
# ═══════════════════════════════════════════════════════════════════════════

app = modal.App("esapiens-compute")

compute_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install(
        "langgraph>=1.0.0",
        "langchain-openai>=0.3.0",
        "langchain-core>=0.3.0",
        "langgraph-checkpoint-sqlite>=1.0.0",
        "httpx>=0.27.0",
        "python-dotenv>=1.0.0",
        "numpy>=1.26.0",
        "matplotlib>=3.8.0",
        "seaborn>=0.13.0",
        "pandas>=2.0.0",
        "plotly>=5.0.0",
        "biopython>=1.83",
        "rdkit-pypi>=2024.3.1",
        "scanpy>=1.10.0",
    )
    .copy_local_dir("bioSkills", "/app/bioSkills")
)

# Persistent volume for workspace data (plots, datasets, checkpoints)
vol = modal.Volume.from_name("esapiens-data", create_if_missing=True)


# ═══════════════════════════════════════════════════════════════════════════
# Compute Engine — Stateful class with lifecycle hooks
# ═══════════════════════════════════════════════════════════════════════════

@app.cls(
    image=compute_image,
    secrets=[modal.Secret.from_name("esapiens-secrets")],
    volumes={"/data": vol},
    timeout=300,
    container_idle_timeout=180,
    min_containers=1,
    allow_port=8000,
)
class ComputeEngine:
    """Stateful compute engine that loads the agent on container startup."""

    @modal.enter()
    def setup(self):
        """Initialize agent graph, tools, and checkpointer on container start."""
        import sys
        sys.path.insert(0, "/app")

        from agent import WorkflowState, build_agent_graph, classify_tier, direct_llm_response, QueryTier
        from tools import TOOL_DEFINITIONS, TOOL_IMPLS, execute_tool
        from intent_classifier import classify_query
        from skill_loader import get_skill_loader, SkillContextBuilder
        from langgraph.checkpoint.sqlite import SqliteSaver

        # Setup checkpoint storage on Modal Volume
        os.makedirs("/data/checkpoints", exist_ok=True)
        self._conn = sqlite3.connect(
            "/data/checkpoints/agent_checkpoints.db",
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._checkpointer = SqliteSaver(self._conn)
        self.agent_graph = build_agent_graph(checkpointer=self._checkpointer)
        self.classify_query = classify_query
        self.classify_tier = classify_tier
        self.direct_llm_response = direct_llm_response
        self.QueryTier = QueryTier
        self.execute_tool = execute_tool
        self.WorkflowState = WorkflowState

        # Skill loading
        self.skill_loader = get_skill_loader(base_path=Path("/app/bioSkills"))
        self.context_builder = SkillContextBuilder(self.skill_loader)

        # Set data dir for tools
        os.environ["ESAPIENS_DATA_DIR"] = "/data"

        print("[ComputeEngine] Agent loaded and ready.")

    @modal.method()
    def classify_intent(self, query: str) -> list[str]:
        """Classify query intent and return skill paths."""
        return self.classify_query(query)

    @modal.method()
    def run_sync(self, query: str, session_id: str, skill_paths: list[str]) -> dict:
        """Run agent synchronously — returns final result dict.

        Routes DIRECT-tier queries through the fast path (no agent loop).
        """
        tier = self.classify_tier(query, skill_paths)

        if tier == self.QueryTier.DIRECT:
            # ── Fast path: direct LLM call, no agent loop ──────────
            response_text = self.direct_llm_response(query)
            return {
                "response": response_text,
                "skills": skill_paths,
                "tool_calls": [],
                "tier": tier.value,
            }

        # ── Standard/Heavy: full ReAct agent loop ──────────────────
        initial_state = {
            "messages": [],
            "query": query,
            "result": "",
            "loaded_skills": skill_paths,
            "tool_calls": [],
        }
        run_config = {"configurable": {"thread_id": session_id}}
        result_state = self.agent_graph.invoke(initial_state, run_config)
        return {
            "response": result_state.get("result", ""),
            "skills": result_state.get("loaded_skills", []),
            "tool_calls": result_state.get("tool_calls", []),
            "tier": tier.value,
        }

    @modal.method()
    def run_stream_events(self, query: str, session_id: str, skill_paths: list[str]) -> list[dict]:
        """
        Run agent and return ALL events as a JSON-serializable list.
        Used by the VPS orchestrator when SSE proxying is not available.
        """
        events = []
        for event in self._stream_generator(query, session_id, skill_paths):
            events.append(event)
        return events

    def _stream_generator(self, query: str, session_id: str, skill_paths: list[str]) -> Generator[dict, None, None]:
        """Core streaming generator — yields event dicts.

        Routes DIRECT-tier queries through the fast path.
        """
        tier = self.classify_tier(query, skill_paths)

        # ── Fast path: direct LLM, no agent loop ──────────────────────
        if tier == self.QueryTier.DIRECT:
            yield {"event": "thought", "data": json.dumps({"message": "Direct response — skipping agent loop..."})}
            yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths})}
            response_text = self.direct_llm_response(query)
            yield {"event": "chunk", "data": json.dumps({"content": response_text, "replace": True})}
            yield {"event": "done", "data": json.dumps({
                "response": response_text,
                "session_id": session_id,
                "skills": skill_paths,
                "tool_calls": [],
                "tier": tier.value,
            })}
            return

        # ── Standard/Heavy: full agent loop ─────────────────────────────
        yield {"event": "thought", "data": json.dumps({"message": f"Route: {tier.value} — engaging full agent loop..."})}
        yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths})}

        initial_state = {
            "messages": [],
            "query": query,
            "result": "",
            "loaded_skills": skill_paths,
            "tool_calls": [],
        }
        run_config = {"configurable": {"thread_id": session_id}}

        collected_tool_calls: list[dict] = []
        collected_skills: list[str] = skill_paths
        collected_visualization: Optional[dict] = None

        try:
            for event in self.agent_graph.stream(initial_state, run_config):
                for event_type, event_data in event.items():
                    if "classify_intent" in event_type:
                        yield {"event": "thought", "data": json.dumps({"message": "Configuring system persona and skill context..."})}
                    elif "call_model" in event_type:
                        yield {"event": "thought", "data": json.dumps({"message": "Consulting large language models for trajectory analysis..."})}
                        node_data = event_data if isinstance(event_data, dict) else {}
                        msgs = node_data.get("messages", [])
                        if msgs:
                            last = msgs[-1]
                            if last.tool_calls:
                                yield {"event": "thought", "data": json.dumps({"message": f"Planning {len(last.tool_calls)} computation steps: {', '.join(tc['name'] for tc in last.tool_calls)}"})}
                            if hasattr(last, "content") and last.content:
                                yield {"event": "chunk", "data": json.dumps({"content": last.content, "replace": True})}
                    elif "tools_node" in event_type:
                        yield {"event": "thought", "data": json.dumps({"message": "Engaging Modal cloud hardware for tool execution..."})}
                        node_data = event_data if isinstance(event_data, dict) else {}
                        for tc in node_data.get("tool_calls", []):
                            name = tc["name"]
                            args = tc.get("args", {})
                            result_str = tc.get("result", "")

                            safe_result = result_str
                            if len(safe_result) > 15000:
                                safe_result = safe_result[:15000] + "\n\n[... output truncated for history persistence ...]"

                            collected_tool_calls.append({
                                "id": tc.get("id", ""),
                                "name": name,
                                "args": args,
                                "result": safe_result,
                                "status": "success",
                            })

                            yield {"event": "thought", "data": json.dumps({"message": f"Executing tool: {name}"})}
                            yield {"event": "tool_call", "data": json.dumps({"name": name, "args": args})}

                            vis_data = None
                            if result_str:
                                try:
                                    result_parsed = json.loads(result_str)
                                    vis_data = result_parsed.get("visualization") if isinstance(result_parsed, dict) else None
                                except (json.JSONDecodeError, TypeError):
                                    pass
                            if vis_data:
                                collected_visualization = vis_data
                                yield {"event": "visualization", "data": json.dumps(vis_data)}

                            yield {"event": "tool_result", "data": json.dumps({"id": tc.get("id", ""), "name": name, "result": result_str, "status": "success"})}
                    elif "finalize" in event_type:
                        yield {"event": "thought", "data": json.dumps({"message": "Synthesizing final scientific report..."})}
                        if isinstance(event_data, dict):
                            collected_skills = event_data.get("loaded_skills", collected_skills)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Modal compute stream error")
            yield {"event": "error", "data": json.dumps({"message": f"An internal error occurred: {str(e)}"})}
            return

        # Get final result
        try:
            final_state = self.agent_graph.get_state(run_config)
            result_text = ""
            if final_state and final_state.values:
                result_text = final_state.values.get("result", "")
        except Exception:
            result_text = ""

        yield {"event": "done", "data": json.dumps({
            "response": result_text,
            "session_id": session_id,
            "skills": collected_skills,
            "tool_calls": collected_tool_calls,
            "visualization": collected_visualization,
            "tier": tier.value,
        })}


# ═══════════════════════════════════════════════════════════════════════════
# ASGI Web Endpoint — for direct SSE streaming from Modal
# ═══════════════════════════════════════════════════════════════════════════

from pathlib import Path


@app.function(
    image=compute_image,
    secrets=[modal.Secret.from_name("esapiens-secrets")],
    volumes={"/data": vol},
    timeout=300,
    container_idle_timeout=180,
    min_containers=1,
    allow_port=8000,
)
@modal.asgi_app()
def compute_api():
    """
    FastAPI app deployed on Modal for SSE streaming agent execution.
    The VPS orchestrator calls this endpoint to proxy events to the frontend.
    """
    import sys
    sys.path.insert(0, "/app")

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    from sse_starlette.sse import EventSourceResponse
    from agent import WorkflowState, build_agent_graph, classify_tier, direct_llm_response, QueryTier
    from tools import TOOL_DEFINITIONS, TOOL_IMPLS, execute_tool
    from intent_classifier import classify_query
    from skill_loader import get_skill_loader, SkillContextBuilder
    from langgraph.checkpoint.sqlite import SqliteSaver

    os.environ["ESAPIENS_DATA_DIR"] = "/data"

    api = FastAPI(title="E.sapiens Compute Engine (Modal)")

    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Setup agent on module load ──────────────────────────────────────
    _conn = sqlite3.connect("/data/checkpoints/agent_checkpoints.db", check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    os.makedirs("/data/checkpoints", exist_ok=True)
    _checkpointer = SqliteSaver(_conn)
    _agent_graph = build_agent_graph(checkpointer=_checkpointer)
    _skill_loader = get_skill_loader(base_path=Path("/app/bioSkills"))
    _context_builder = SkillContextBuilder(_skill_loader)

    # ── Request schemas ─────────────────────────────────────────────────

    class ComputeRequest(BaseModel):
        query: str = Field(..., max_length=10000)
        session_id: str = Field("default", max_length=128)
        skill_paths: list[str] = []
        user_id: str = Field("default", max_length=128)

    # ── Health check ────────────────────────────────────────────────────

    @api.get("/health")
    async def health():
        return {"status": "healthy", "service": "esapiens-compute-modal"}

    # ── Tier classification endpoint ─────────────────────────────────────

    @api.post("/classify")
    async def classify(req: ComputeRequest):
        skill_paths = classify_query(req.query)
        tier = classify_tier(req.query, skill_paths)
        return {"skills": skill_paths, "tier": tier.value}

    # ── Sync execution ──────────────────────────────────────────────────

    @api.post("/compute/sync")
    async def compute_sync(req: ComputeRequest):
        skill_paths = req.skill_paths or classify_query(req.query)
        tier = classify_tier(req.query, skill_paths)

        # ── Fast path: DIRECT tier ─────────────────────────────────────
        if tier == QueryTier.DIRECT:
            response_text = direct_llm_response(req.query)
            return {
                "response": response_text,
                "skills": skill_paths,
                "tool_calls": [],
                "tier": tier.value,
            }

        # ── Standard/Heavy: full agent loop ─────────────────────────────
        initial_state = {
            "messages": [],
            "query": req.query,
            "result": "",
            "loaded_skills": skill_paths,
            "tool_calls": [],
        }
        run_config = {"configurable": {"thread_id": req.session_id}}
        result_state = _agent_graph.invoke(initial_state, run_config)
        return {
            "response": result_state.get("result", ""),
            "skills": result_state.get("loaded_skills", []),
            "tool_calls": result_state.get("tool_calls", []),
            "tier": tier.value,
        }

    # ── Streaming execution (SSE) ───────────────────────────────────────

    @api.post("/compute/stream")
    async def compute_stream(req: ComputeRequest):
        """Run the agent and stream SSE events. Routes DIRECT queries through fast path."""
        skill_paths = req.skill_paths or classify_query(req.query)
        tier = classify_tier(req.query, skill_paths)

        def _stream():
            # ── Fast path: DIRECT tier ─────────────────────────────────────
            if tier == QueryTier.DIRECT:
                yield {"event": "thought", "data": json.dumps({"message": "Direct response — skipping agent loop..."})}
                yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths, "tier": tier.value})}
                response_text = direct_llm_response(req.query)
                yield {"event": "chunk", "data": json.dumps({"content": response_text, "replace": True})}
                yield {"event": "done", "data": json.dumps({
                    "response": response_text,
                    "session_id": req.session_id,
                    "skills": skill_paths,
                    "tool_calls": [],
                    "tier": tier.value,
                })}
                return

            # ── Standard/Heavy: full agent loop ─────────────────────────────
            yield {"event": "thought", "data": json.dumps({"message": f"Route: {tier.value} — engaging full agent loop..."})}
            yield {"event": "skills_loaded", "data": json.dumps({"skills": skill_paths, "tier": tier.value})}
            yield {"event": "thought", "data": json.dumps({"message": "Allocating neural engine threads for scientific reasoning..."})}

            initial_state = {
                "messages": [],
                "query": req.query,
                "result": "",
                "loaded_skills": skill_paths,
                "tool_calls": [],
            }
            run_config = {"configurable": {"thread_id": req.session_id}}

            collected_tool_calls: list[dict] = []
            collected_skills: list[str] = skill_paths
            collected_visualization: Optional[dict] = None

            try:
                for event in _agent_graph.stream(initial_state, run_config):
                    for event_type, event_data in event.items():
                        if "classify_intent" in event_type:
                            yield {"event": "thought", "data": json.dumps({"message": "Configuring system persona and skill context..."})}
                        elif "call_model" in event_type:
                            yield {"event": "thought", "data": json.dumps({"message": "Consulting large language models for trajectory analysis..."})}
                            node_data = event_data if isinstance(event_data, dict) else {}
                            msgs = node_data.get("messages", [])
                            if msgs:
                                last = msgs[-1]
                                if last.tool_calls:
                                    yield {"event": "thought", "data": json.dumps({"message": f"Planning {len(last.tool_calls)} computation steps: {', '.join(tc['name'] for tc in last.tool_calls)}"})}
                                if hasattr(last, "content") and last.content:
                                    yield {"event": "chunk", "data": json.dumps({"content": last.content, "replace": True})}
                        elif "tools_node" in event_type:
                            yield {"event": "thought", "data": json.dumps({"message": "MODAL.COM • Engaging cloud hardware for tool execution..."})}
                            node_data = event_data if isinstance(event_data, dict) else {}
                            for tc in node_data.get("tool_calls", []):
                                name = tc["name"]
                                args = tc.get("args", {})
                                result_str = tc.get("result", "")

                                safe_result = result_str
                                if len(safe_result) > 15000:
                                    safe_result = safe_result[:15000] + "\n\n[... output truncated ...]"

                                collected_tool_calls.append({
                                    "id": tc.get("id", ""),
                                    "name": name,
                                    "args": args,
                                    "result": safe_result,
                                    "status": "success",
                                })

                                yield {"event": "thought", "data": json.dumps({"message": f"MODAL.COM • Executing tool: {name}"})}
                                yield {"event": "tool_call", "data": json.dumps({"name": name, "args": args})}

                                vis_data = None
                                if result_str:
                                    try:
                                        result_parsed = json.loads(result_str)
                                        vis_data = result_parsed.get("visualization") if isinstance(result_parsed, dict) else None
                                    except (json.JSONDecodeError, TypeError):
                                        pass
                                if vis_data:
                                    collected_visualization = vis_data
                                    yield {"event": "visualization", "data": json.dumps(vis_data)}

                                yield {"event": "tool_result", "data": json.dumps({"id": tc.get("id", ""), "name": name, "result": result_str, "status": "success"})}
                        elif "finalize" in event_type:
                            yield {"event": "thought", "data": json.dumps({"message": "Synthesizing final scientific report..."})}
                            if isinstance(event_data, dict):
                                collected_skills = event_data.get("loaded_skills", collected_skills)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception("Modal compute stream error")
                yield {"event": "error", "data": json.dumps({"message": f"Modal compute error: {str(e)}"})}
                return

            # Final result
            try:
                final_state = _agent_graph.get_state(run_config)
                result_text = ""
                if final_state and final_state.values:
                    result_text = final_state.values.get("result", "")
            except Exception:
                result_text = ""

            yield {"event": "done", "data": json.dumps({
                "response": result_text,
                "session_id": req.session_id,
                "skills": collected_skills,
                "tool_calls": collected_tool_calls,
                "visualization": collected_visualization,
                "tier": tier.value,
            })}

        return EventSourceResponse(_stream())

    return api


# ═══════════════════════════════════════════════════════════════════════════
# Local entrypoint — for testing with `modal run`
# ═══════════════════════════════════════════════════════════════════════════

@app.local_entrypoint()
def test_compute(query: str = "What is the structure of hemoglobin?"):
    """Test the compute engine locally with `modal run modal_compute.py`"""
    engine = ComputeEngine()
    skills = engine.classify_intent.remote(query)
    print(f"Skills: {skills}")
    result = engine.run_sync.remote(query, "test-session", skills)
    print(f"Result: {result['response'][:200]}...")
