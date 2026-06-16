"""Supervisor agent — hub-and-spoke multi-agent architecture.

The Supervisor is a single LLM that:
  1. Reflects on the user's question
  2. Decides which subagent(s) to delegate to (if any)
  3. Loops: delegate → receive findings → reflect → delegate more, or finish
  4. Synthesizes a final answer from all subagent findings

Workers do NOT communicate with each other. They only report back to the
Supervisor via the LangGraph `messages` channel.

Graph topology:
    supervisor → (decides) → tools (subagent invocation)
                            ↓
    supervisor ← (findings) ← tools
                            ↓
    END       ← (done)    ← supervisor

This replaces the linear PLANNER → CONSTRUCTOR → CRITIC → HITL flow
for the conversational layer. The pipeline construction path (when the
Supervisor decides the user wants to build a pipeline) is still handled
by the existing `AgentService`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from app.services.llm import get_llm
from app.services.subagents import (
    SUBAGENT_TOOLS,
    SubagentResult,
    SubagentRole,
    invoke_subagent,
    synthesize_findings,
)

logger = logging.getLogger(__name__)


# ── Supervisor state ─────────────────────────────────────────────────────


class SupervisorPhase(str, Enum):
    """Phases the supervisor moves through."""

    REFLECTING = "reflecting"   # Thinking about the question
    DELEGATING = "delegating"   # Calling subagents
    SYNTHESIZING = "synthesizing"  # Composing final answer
    DONE = "done"


class SupervisorDecision(BaseModel):
    """The Supervisor's structured output for each turn.

    Forces the LLM to either:
      - Call one of the subagent tools (via tool-calling), OR
      - Emit a structured 'finalize' decision
    """

    action: Literal["delegate", "finalize"]
    reasoning: str = Field(..., description="Why this action")
    final_answer: str | None = Field(
        default=None, description="If action=finalize, the answer for the user"
    )


class SupervisorState(BaseModel):
    """State flowing through the Supervisor graph.

    Tracks: the original question, messages exchanged, subagent findings,
    iteration count (to prevent infinite loops), and the final answer.
    """

    # ── Input ──────────────────────────────────────────────────────
    session_id: uuid.UUID
    user_id: uuid.UUID
    original_prompt: str
    grant_id: uuid.UUID | None = None

    # ── Conversation ───────────────────────────────────────────────
    # Full message history (HumanMessage, AIMessage, ToolMessage)
    messages: list[dict[str, Any]] = Field(default_factory=list)

    # ── Subagent results collected so far ──────────────────────────
    subagent_results: list[SubagentResult] = Field(default_factory=list)

    # ── Reflection ─────────────────────────────────────────────────
    reflection: str = Field(default="", description="Supervisor's current thinking")
    phase: SupervisorPhase = SupervisorPhase.REFLECTING

    # ── Iteration control ──────────────────────────────────────────
    iteration: int = 0
    max_iterations: int = 5  # prevent infinite tool-call loops

    # ── Final answer ───────────────────────────────────────────────
    final_answer: str | None = None

    # ── Error handling ─────────────────────────────────────────────
    error_log: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


# ── Supervisor node ──────────────────────────────────────────────────────


SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor of the E.sapiens multi-agent system.

Your job is to assist the user with scientific and bioinformatics questions by
coordinating a team of specialized subagents. You do NOT do the work yourself —
you delegate.

Subagents available to you:
  - biology_agent:   gene function, pathways, genomics, proteomics, experimental design
  - math_agent:      statistical tests, power analysis, Bayesian modeling, effect sizes
  - code_agent:      Python/bash code, pipeline construction, data wrangling, APIs
                     (BLOCKING — returns when code finishes, may take up to 30s)
  - literature_agent: paper search, citations, evidence summarization
  - async_dispatch_agent: NON-BLOCKING — dispatches a long-running job to Modal
                     and returns a job_id immediately. Use for heavy compute
                     (deep learning training, large dataset analysis, long
                     simulations) that would take more than 30 seconds.
                     The user can keep chatting while it runs.
  - async_status_agent:  Check the status of a previously-dispatched async job.
                     Returns current progress, and (if complete) full stdout.

Workflow:
  1. REFLECT on the user's question. What do they actually need?
  2. DECIDE: do I have enough context, or should I delegate?
  3. If delegating, call the appropriate subagent tool(s) with a focused task.
  4. For LONG-running jobs (>30s), use async_dispatch_agent instead of code_agent.
     Tell the user the job is running, give them the job_id, and offer to
     follow up when it's done.
  5. After receiving findings, REFLECT again. Is more info needed?
  6. When the user asks "is it done?" or "what's the result?", use
     async_status_agent with the job_id to fetch the latest state and
     synthesize a final report from the results.
  7. When done, synthesize a final answer for the user.

Rules:
  - You may call multiple subagents in parallel if the question spans domains.
  - Do NOT call the same subagent more than twice with the same task.
  - Do NOT ask the user clarifying questions unless absolutely necessary — make
    reasonable assumptions and state them.
  - When you have enough information, call `finalize` with the synthesized answer.
  - Workers do not talk to each other. You are the only coordinator.
  - Be concise. The user wants an answer, not a thesis.
"""


async def _supervisor_node(state: SupervisorState) -> dict[str, Any]:
    """The Supervisor's main reasoning node.

    Decides: delegate to a subagent, or finalize with an answer.
    """
    import asyncio

    llm = get_llm()
    if llm is None:
        # No LLM — return a canned response
        return {
            "reflection": "LLM unavailable, cannot reason about delegation",
            "final_answer": "The Supervisor LLM is not configured. Please set OPENROUTER_API_KEY.",
            "phase": SupervisorPhase.DONE.value,
        }

    # Increment iteration
    new_iteration = state.iteration + 1
    if new_iteration > state.max_iterations:
        # Hit max iterations — synthesize what we have
        logger.warning("Supervisor hit max_iterations=%d, forcing finalize", state.max_iterations)
        final = await synthesize_findings(state.original_prompt, state.subagent_results)
        return {
            "iteration": new_iteration,
            "final_answer": final,
            "phase": SupervisorPhase.DONE.value,
        }

    # Bind subagent tools to the LLM
    llm_with_tools = llm.bind_tools(SUBAGENT_TOOLS) if SUBAGENT_TOOLS else llm

    # Build message history
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    lc_messages: list[Any] = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT)]

    # Add subagent results as prior context (so the LLM knows what it already learned)
    if state.subagent_results:
        prior_context = "\n\n".join(
            f"[{r.role.value} subagent] {r.findings}"
            + (f"\nData: {json.dumps(r.structured_data, default=str)[:300]}" if r.structured_data else "")
            for r in state.subagent_results
        )
        lc_messages.append(
            HumanMessage(
                content=f"User question: {state.original_prompt}\n\nFindings so far:\n{prior_context}\n\nDecide: delegate to another subagent, or finalize?"
            )
        )
    else:
        lc_messages.append(HumanMessage(content=f"User question: {state.original_prompt}"))

    # Add any prior LLM messages
    lc_messages.extend(state.messages)

    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(lc_messages),
            timeout=30.0,
        )
    except Exception as exc:
        # asyncio.TimeoutError has empty str() — show the timeout value
        if isinstance(exc, asyncio.TimeoutError):
            err_msg = f"LLM call timed out after 30s"
        else:
            err_msg = f"{type(exc).__name__}: {exc}"
        logger.warning("Supervisor LLM call failed: %s", err_msg)
        return {
            "iteration": new_iteration,
            "error_log": state.error_log + [f"Supervisor LLM error: {err_msg}"],
            "reflection": f"LLM error: {err_msg}",
            "phase": SupervisorPhase.SYNTHESIZING.value,
        }

    # Extract tool calls and content
    tool_calls = getattr(response, "tool_calls", []) or []
    content = getattr(response, "content", "") or ""
    if not isinstance(content, str):
        content = str(content)

    # If the LLM decided to call a subagent, route to the tools node
    if tool_calls:
        return {
            "iteration": new_iteration,
            "messages": state.messages + [
                {"role": "assistant", "content": content, "tool_calls": tool_calls}
            ],
            "reflection": content or "Delegating to subagent(s)",
            "phase": SupervisorPhase.DELEGATING.value,
        }

    # No tool calls — the LLM is finalizing
    # If the content is a structured finalize decision, parse it
    final_answer = content
    if content.strip():
        try:
            decision = SupervisorDecision.model_validate_json(content)
            if decision.action == "finalize" and decision.final_answer:
                final_answer = decision.final_answer
        except Exception:
            # Content is plain text, treat as final answer
            pass

    # Safety net: if the LLM produced no content at all and we have
    # subagent results, synthesize from those. Otherwise we'd return
    # "I could not generate a response" for an otherwise successful run.
    if not final_answer.strip() and state.subagent_results:
        try:
            final_answer = await synthesize_findings(
                state.original_prompt, state.subagent_results
            )
        except Exception as exc:
            logger.warning("Synthesis fallback failed: %s", exc)
            # Last resort: concatenate findings
            final_answer = "\n\n".join(
                f"[{r.role.value}] {r.findings}" for r in state.subagent_results
            )

    # Last-resort fallback: if still empty, ask the LLM directly for a plain answer
    if not final_answer.strip() and llm is not None:
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            rescue = await asyncio.wait_for(
                llm.ainvoke(
                    [
                        SystemMessage(
                            content="You are a helpful scientific assistant. Answer the user's question concisely based on your own knowledge. Be honest about uncertainty."
                        ),
                        HumanMessage(content=state.original_prompt),
                    ]
                ),
                timeout=20.0,
            )
            rescue_content = getattr(rescue, "content", "") or ""
            if isinstance(rescue_content, str) and rescue_content.strip():
                final_answer = rescue_content.strip()
        except Exception as exc:
            if isinstance(exc, asyncio.TimeoutError):
                logger.warning("Rescue LLM call failed: timed out after 20s")
            else:
                logger.warning("Rescue LLM call failed: %s", exc)

    return {
        "iteration": new_iteration,
        "messages": state.messages + [{"role": "assistant", "content": final_answer}],
        "reflection": "Finalizing answer",
        "final_answer": final_answer,
        "phase": SupervisorPhase.DONE.value,
    }


# ── Subagent tool wrapper node ───────────────────────────────────────────


async def _tools_node(state: SupervisorState) -> dict[str, Any]:
    """Execute the subagent tool calls the Supervisor requested.

    Uses LangGraph's ToolNode to invoke the subagent tools. Each tool
    invocation adds a ToolMessage to the message history, which the
    Supervisor reads on the next iteration.
    """
    if not SUBAGENT_TOOLS:
        return {
            "error_log": state.error_log + ["No subagent tools available"],
            "phase": SupervisorPhase.SYNTHESIZING.value,
        }

    # Extract the last AIMessage's tool calls
    last_msg = state.messages[-1] if state.messages else {}
    tool_calls = last_msg.get("tool_calls", []) if isinstance(last_msg, dict) else []

    if not tool_calls:
        return {"phase": SupervisorPhase.SYNTHESIZING.value}

    # Invoke each subagent in parallel
    results: list[SubagentResult] = []
    new_messages: list[dict[str, Any]] = []

    async def _run_one(tc: dict[str, Any]) -> tuple[SubagentResult, dict[str, Any]]:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool_call_id = tc.get("id", f"call_{uuid.uuid4().hex[:8]}")
        task = tool_args.get("task", state.original_prompt)
        context = tool_args.get("context", "")

        # Auto-inject session_id and user_id into the context so async tools
        # can route the job to the right session. This is appended at the end
        # in a JSON fragment that the tool's regex can extract.
        if tool_name in ("async_dispatch_agent", "async_status_agent"):
            context = (
                context
                + (
                    f"\n\n[Session context: "
                    f'{{"session_id": "{state.session_id}", "user_id": "{state.user_id}"}}'
                    f"]"
                )
            )

        # Map tool name → SubagentRole
        role_map = {
            "biology_agent": SubagentRole.BIOLOGY,
            "math_agent": SubagentRole.MATH,
            "code_agent": SubagentRole.CODE,
            "literature_agent": SubagentRole.LITERATURE,
        }
        role = role_map.get(tool_name)
        if role is None:
            result = SubagentResult(
                role=SubagentRole.BIOLOGY,  # fallback
                task=task,
                findings=f"Unknown subagent tool: {tool_name}",
                confidence=0.0,
            )
        else:
            result = await invoke_subagent(role, task, context)

        result.tool_call_id = tool_call_id
        tool_msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result.model_dump_json(),
        }
        return result, tool_msg

    outcomes = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
    for r, m in outcomes:
        results.append(r)
        new_messages.append(m)

    return {
        "subagent_results": state.subagent_results + results,
        "messages": state.messages + new_messages,
        "phase": SupervisorPhase.REFLECTING.value,
    }


# ── Graph wiring ─────────────────────────────────────────────────────────


def _route_after_supervisor(state: SupervisorState) -> str:
    """Decide where to go after the supervisor node."""
    if state.phase == SupervisorPhase.DONE.value or state.final_answer:
        return END
    if state.phase == SupervisorPhase.DELEGATING.value:
        return "tools"
    return END


def _route_after_tools(state: SupervisorState) -> str:
    """After tools run, go back to the supervisor for another decision."""
    return "supervisor"


def build_supervisor_graph() -> StateGraph:
    """Construct the Supervisor's StateGraph.

    Topology:
        supervisor → tools → supervisor → ... → END
    """
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("supervisor", _supervisor_node)
    graph.add_node("tools", _tools_node)

    # Set entry point
    graph.set_entry_point("supervisor")

    # Conditional edges from supervisor
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"tools": "tools", END: END},
    )

    # After tools, always go back to supervisor
    graph.add_edge("tools", "supervisor")

    return graph


# ── Service wrapper ──────────────────────────────────────────────────────


class SupervisorService:
    """Public interface for invoking the Supervisor from routers."""

    def __init__(self) -> None:
        self._graph = build_supervisor_graph().compile()

    async def run(
        self,
        prompt: str,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        grant_id: uuid.UUID | None = None,
    ) -> SupervisorState:
        """Run the Supervisor on a user prompt.

        Returns the final SupervisorState with subagent_results populated
        and final_answer set.
        """
        initial = SupervisorState(
            session_id=session_id,
            user_id=user_id,
            original_prompt=prompt,
            grant_id=grant_id,
            messages=[{"role": "user", "content": prompt}],
        )
        config = {"recursion_limit": 20}
        result = await self._graph.ainvoke(initial, config=config)
        if isinstance(result, dict):
            return SupervisorState(**result)
        return result

    async def run_synthesis_only(
        self,
        prompt: str,
        subagent_results: list[SubagentResult],
    ) -> str:
        """Bypass the graph and just synthesize findings into an answer."""
        return await synthesize_findings(prompt, subagent_results)