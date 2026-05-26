"""
Agent Node Definitions — LangGraph ReAct loop nodes.

Defines WorkflowState TypedDict, the call_model and tools_node,
the graph builder function for the E.sapiens v2 agent,
and a tiered query router for fast-pathing simple queries.
"""

import os
import re
from enum import Enum
from typing import Annotated, Any, Literal, Sequence, TypedDict

import operator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from tools import TOOL_DEFINITIONS, execute_tool
from prompts import (
    get_prompt,
    get_model_config,
    get_style_rules,
    get_prompt_meta,
    build_skill_context_block,
    build_tool_definitions_block,
    build_output_format_block,
    build_specialist_guidance,
)
from compress import compress_messages, should_compress, count_tokens

# ── Tiered Query Routing ────────────────────────────────────────────────────


class QueryTier(str, Enum):
    """Routing tier for incoming queries.

    DIRECT   — greetings, meta-questions, simple definitions → fast LLM, no tools
    STANDARD — bio queries that need tools → full ReAct loop with skill context
    HEAVY    — multi-step pipelines, plots → full ReAct loop (may iterate)
    """
    DIRECT = "direct"
    STANDARD = "standard"
    HEAVY = "heavy"


# Patterns that indicate a DIRECT (fast-path) query — no tools needed
_DIRECT_PATTERNS = re.compile(
    r"^(hi|hello|hey|good\s*(morning|evening|afternoon|night)|what'?s?\s*up|sup|thanks|thank\s*you|ty|bye|goodbye|ok|okay|yes|no|sure|got\s*it|sounds?\s*good|cool|great|nice|awesome|right|exactly|understood|gotcha|roger|agreed|please|pls|help|how\s*are\s*you|who\s*are\s*you|what\s*(can|do)\s*you\s*do)\b",
    re.IGNORECASE,
)

# Short, simple definition patterns — "what is X", "define X", "explain X briefly"
_SIMPLE_DEFINITION = re.compile(
    r"^(what\s+is|what'?s|define|explain\s+briefly|tell\s+me\s+about|describe)\s+\w+",
    re.IGNORECASE,
)

# Queries that imply multi-step computation
_HEAVY_PATTERNS = re.compile(
    r"\b(pipeline|workflow|compare|benchmark|analyze\s+and\s+plot|multi[- ]?step|end[- ]?to[- ]?end|integrate|correlate\s+.*\band\b|download\s+.*\band\s+(plot|visualize|align|run))\b",
    re.IGNORECASE,
)


def classify_tier(query: str, skill_paths: list[str] | None = None) -> QueryTier:
    """Classify a query into DIRECT / STANDARD / HEAVY.

    Logic:
      1. If query matches greeting/meta patterns → DIRECT
      2. If query is a short simple definition AND no skills matched → DIRECT
      3. If query matches multi-step patterns OR multiple skills matched → HEAVY
      4. Otherwise → STANDARD
    """
    q = query.strip()

    # 1. Pure greetings / meta → DIRECT
    if _DIRECT_PATTERNS.match(q):
        return QueryTier.DIRECT

    # Determine skill match count
    num_skills = len(skill_paths) if skill_paths else 0

    # 2. Simple definition with no bio skills → DIRECT
    if _SIMPLE_DEFINITION.match(q) and num_skills == 0 and len(q.split()) <= 12:
        return QueryTier.DIRECT

    # 3. Multi-step or heavy computation → HEAVY
    if _HEAVY_PATTERNS.search(q) or num_skills >= 3:
        return QueryTier.HEAVY

    # 4. Default → STANDARD
    return QueryTier.STANDARD


# ── Fast-path: direct LLM call (no tools, minimal prompt) ────────────────────

DIRECT_MODEL = os.getenv("OPENROUTER_DIRECT_MODEL", "")  # optional fast model override


def direct_llm_response(query: str) -> str:
    """Fast-path: call the LLM directly with no tools, no skill context.

    Used for DIRECT-tier queries (greetings, simple definitions, meta).
    Returns the response text directly — no agent loop, no tool calls.
    """
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key.startswith("sk-or-v1-placeholder"):
        return get_prompt(
            "mock_response",
            query=query,
            tool_names=", ".join(t["name"] for t in TOOL_DEFINITIONS),
        )

    model = DIRECT_MODEL or chosen_model
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        model=model,
        temperature=0.3,
        timeout=30,  # aggressive timeout for fast-path
        max_tokens=1024,
        default_headers={
            "HTTP-Referer": "https://echosapiens.bio",
            "X-Title": "E.sapiens v2 Direct",
        },
    )
    messages = [
        SystemMessage(content=get_prompt("direct")),
        HumanMessage(content=query),
    ]
    response = llm.invoke(messages)
    return response.content or ""


# ── Agent state ──────────────────────────────────────────────────────────────

# set chosen_model from environment variable.
chosen_model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash:exacto")
class WorkflowState(TypedDict):
    """State passed between nodes in the ReAct loop."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    query: str
    result: str
    loaded_skills: list[str]
    tool_calls: list[dict[str, Any]]


# ── LLM setup ────────────────────────────────────────────────────────────────

_openrouter_api_key: str | None = os.getenv("OPENROUTER_API_KEY")


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI instance pointed at OpenRouter."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_openrouter_api_key or "sk-or-v1-placeholder",
        model=chosen_model,
        temperature=0.0,
        timeout=120,
        default_headers={
            "HTTP-Referer": "https://echosapiens.bio",
            "X-Title": "E.sapiens v2 Agent",
        },
    )


# ── Node: classify_intent ────────────────────────────────────────────────────


def classify_intent_node(state: WorkflowState) -> dict:
    """
    First node: classify the user query, load relevant skills,
    and inject skill context into the system prompt.
    """
    from intent_classifier import classify_query
    from skill_loader import get_skill_loader, SkillContextBuilder
    from pathlib import Path

    query = state["query"]
    skill_paths = classify_query(query)

    bioskills_path = Path(__file__).parent.parent / "bioSkills"
    loader = get_skill_loader(bioskills_path)
    builder = SkillContextBuilder(loader)
    skills_context = builder.build_context(skill_paths, max_length=6000)

    # Build the system message with skill context
    tool_definitions_str = "\n".join(
        f"  - {t['name']}: {t['description']}" for t in TOOL_DEFINITIONS
    )
    system_content = get_prompt(
        "standard",
        skill_context_block=build_skill_context_block(
            skills_context if skills_context else "(no skill context)"
        ),
        tool_definitions_block=build_tool_definitions_block(tool_definitions_str),
        output_format_block=build_output_format_block(),
        specialist_guidance=build_specialist_guidance("standard"),
    )

    system_msg = SystemMessage(
        content=system_content,
    )
    # Only add system message if not already present in state
    has_system = any(isinstance(msg, SystemMessage) for msg in state.get("messages", []))
    new_messages = []
    if not has_system:
        new_messages.append(system_msg)
    new_messages.append(HumanMessage(content=query))

    return {
        "messages": new_messages,
        "loaded_skills": skill_paths,
    }


# ── Node: call_model ─────────────────────────────────────────────────────────


def _is_placeholder_key() -> bool:
    """Check if the OpenRouter API key is a placeholder."""
    key = _openrouter_api_key or ""
    return not key or key.startswith("sk-or-v1-placeholder")


def _mock_llm_response(state: WorkflowState) -> AIMessage:
    """Return a mock response when no real LLM key is configured."""
    query = state.get("query", "")
    # Extract last user message content — handle LangChain's list content type
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and msg.content:
            raw = msg.content
            query = raw if isinstance(raw, str) else str(raw[0]) if raw else ""
            break

    content = get_prompt(
        "mock_response",
        query=query,
        tool_names=", ".join(t["name"] for t in TOOL_DEFINITIONS),
    )
    return AIMessage(content=content)


def call_model(state: WorkflowState) -> dict:
    """Call the LLM with the current conversation and return the response.

    Before invoking the LLM, compresses the message history if it exceeds
    80% of the model's context window to prevent token overflow errors.
    """
    if _is_placeholder_key():
        response = _mock_llm_response(state)
        return {"messages": [response]}

    llm = get_llm()

    # ── Context compression ──────────────────────────────────────────────
    # Compress message history if it exceeds the model's context threshold.
    # This prevents 400 errors from token overflow on long conversations.
    messages = list(state["messages"])
    if should_compress(messages, chosen_model):
        compressed = compress_messages(
            messages,
            model_name=chosen_model,
            openrouter_api_key=_openrouter_api_key,
        )
        if len(compressed) < len(messages):
            print(f"[Compress] {len(messages)} msgs → {len(compressed)} "
                  f"({count_tokens(messages)} → {count_tokens(compressed)} tokens)")
            messages = compressed

    # Bind tools so the model can request function calls
    try:
        llm_with_tools = llm.bind_tools(TOOL_DEFINITIONS)
        response = llm_with_tools.invoke(messages)
    except Exception as e:
        err_str = str(e)
        # If provider rejects the tool definitions, try without tools
        if "400" in err_str or "BadRequest" in err_str or "tool" in err_str.lower():
            print(f"[Agent] Tool binding rejected by provider ({e.__class__.__name__}), retrying without tools")
            try:
                response = llm.invoke(messages)
            except Exception as e2:
                print(f"[Agent] LLM invocation failed: {e2}")
                return {"messages": [AIMessage(content="I encountered an error processing your request. Please try again.")]}
        else:
            print(f"[Agent] LLM invocation failed: {e}")
            return {"messages": [AIMessage(content="I encountered an error processing your request. Please try again.")]}
    return {"messages": [response]}


# ── Node: tools_node ─────────────────────────────────────────────────────────


def tools_node(state: WorkflowState) -> dict:
    """
    Execute tool calls requested by the model.
    Returns ToolMessage results appended to the message list.
    """
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": [], "tool_calls": []}

    tool_messages: list[ToolMessage] = []
    tool_calls_record: list[dict] = []

    for tc in last_message.tool_calls:
        name = tc["name"]
        args = tc.get("args", {})
        tool_call_id = tc.get("id", "")

        print(f"[Agent] Executing tool: {name}({args})")
        result_str = execute_tool(name, args)

        tool_messages.append(
            ToolMessage(content=result_str, tool_call_id=tool_call_id, name=name)
        )
        tool_calls_record.append({"name": name, "args": args, "result": result_str})

    return {"messages": tool_messages, "tool_calls": tool_calls_record}


# ── Edge: should_continue ────────────────────────────────────────────────────


def should_continue(state: WorkflowState) -> Literal["tools_node", "finalize"]:
    """Decide whether to loop back to tools or finalize."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools_node"
    return "finalize"


# ── Node: finalize ───────────────────────────────────────────────────────────


def finalize_node(state: WorkflowState) -> dict:
    """Extract the final answer from the last AI message."""
    last_message = state["messages"][-1]
    result = ""
    if isinstance(last_message, AIMessage):
        result = last_message.content or ""
    return {"result": result}


# ── Graph builder ────────────────────────────────────────────────────────────


def build_agent_graph(checkpointer=None) -> StateGraph:
    """Build and compile the LangGraph ReAct agent.

    Args:
        checkpointer: A LangGraph checkpointer instance (e.g., SqliteSaver).
                      If None, uses SqliteSaver with ':memory:'.
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("call_model", call_model)
    workflow.add_node("tools_node", tools_node)
    workflow.add_node("finalize", finalize_node)

    # Set entry point
    workflow.set_entry_point("classify_intent")

    # Add edges
    workflow.add_edge("classify_intent", "call_model")
    workflow.add_conditional_edges(
        "call_model",
        should_continue,
        {"tools_node": "tools_node", "finalize": "finalize"},
    )
    workflow.add_edge("tools_node", "call_model")
    workflow.add_edge("finalize", END)

    # Use provided checkpointer or create one with persistent connection
    if checkpointer is None:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        checkpointer = SqliteSaver(conn)

    return workflow.compile(checkpointer=checkpointer)


# Pre-built graph instance
agent_graph = build_agent_graph()