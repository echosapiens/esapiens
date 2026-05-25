"""
Agent Node Definitions — LangGraph ReAct loop nodes.

Defines WorkflowState TypedDict, the call_model and tools_node,
the graph builder function for the E.sapiens v2 agent,
and a tiered query router for fast-pathing simple queries.
"""

import json
import os
import re
from enum import Enum
from typing import Annotated, Any, Callable, Literal, Sequence, TypedDict

import operator

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()

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

_DIRECT_SYSTEM_PROMPT = (
    "You are E.sapiens, a professional bioinformatics research assistant. "
    "Respond concisely and accurately. No emojis. Formal scientific tone."
)

DIRECT_MODEL = os.getenv("OPENROUTER_DIRECT_MODEL", "")  # optional fast model override


def direct_llm_response(query: str) -> str:
    """Fast-path: call the LLM directly with no tools, no skill context.

    Used for DIRECT-tier queries (greetings, simple definitions, meta).
    Returns the response text directly — no agent loop, no tool calls.
    """
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key.startswith("sk-or-v1-placeholder"):
        return "I'm running in offline/demo mode. Please set OPENROUTER_API_KEY for full functionality."

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
        SystemMessage(content=_DIRECT_SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]
    response = llm.invoke(messages)
    return response.content or ""


# ── Agent state ──────────────────────────────────────────────────────────────

# set chosen_model from environment variable.
chosen_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-coder-next:nitro")
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
    system_content = (
        "You are E.sapiens, a professional bioinformatics research assistant.\n\n"
        "STYLE RULES — MANDATORY:\n"
        "- NEVER use emojis, icons, or decorative symbols. This is strictly prohibited.\n"
        "- NO SYNTHETIC DATA: Never use synthetic, mock, or example data. Everything must be real-world data downloaded from biological databases.\n"
        "- Write in clear, formal scientific prose. Prefer precise technical language over casual phrasing.\n"
        "- Use standard hierarchy: title case for headings, sentence case for body text.\n"
        "- Structure responses with numbered steps or concise paragraphs, not stream-of-consciousness.\n"
        "- When presenting data, favor tables, lists, and structured formats over walls of text.\n"
        "- Do not use filler phrases like 'Great question!' or 'Let me help you with that.' — get to the point.\n"
        "- Do not use exclamation marks.\n\n"
        "You have access to the following tools. Use them when needed.\n\n"
        "Available tools:\n"
        + "\n".join(f"  - {t['name']}: {t['description']}" for t in TOOL_DEFINITIONS)
        + "\n\n"
        "TOOL CREATION: If you need a capability that does not exist among your tools "
        "(e.g. downloading from GEO, SRA, ArrayExpress, Ensembl, or other bioinformatics databases), "
        "use the 'create_tool' function to create it. \\n\\n"
        "Guidelines for successful tool creation:\\n"
        "- Signature: Always include **kwargs (e.g., `def my_tool(param1, **kwargs):`).\\n"
        "- Dependencies: Use `httpx` for networking and Biopython (`Bio`) for sequences.\\n"
        "- Persistence: Use the `WORKSPACE` global (Path object) for all file operations.\\n"
        "- Output: Always return a dict. Catch all exceptions and return `{'error': str(e)}`.\\n"
        "- Verification: Never call a tool with empty arguments `{}` if it requires parameters.\\n"
        "- Do NOT tell the user you cannot do something — create the tool yourself.\\n\\n"
        "CODE EXECUTION: For data analysis, file processing, or computations that don't need "
        "a dedicated tool, use 'execute_python'. This gives you a full Python environment with "
        "pandas, numpy, scipy, httpx, and Bio (biopython)."
    )
    if skills_context:
        system_content += f"\n\nRelevant skill context loaded:\n{skills_context}"

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
    # Extract last user message content
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) and msg.content:
            query = msg.content
            break

    mock = (
        f"I'm running in offline/demo mode (no OpenRouter API key configured). "
        f"You asked: \"{query}\".\n\n"
        f"In production, I would use the appropriate bioinformatics tools to "
        f"answer this. Available tools include: "
        f"{', '.join(t['name'] for t in TOOL_DEFINITIONS)}.\n\n"
        f"Please set the OPENROUTER_API_KEY environment variable for full functionality."
    )
    return AIMessage(content=mock)


def call_model(state: WorkflowState) -> dict:
    """Call the LLM with the current conversation and return the response."""
    if _is_placeholder_key():
        response = _mock_llm_response(state)
        return {"messages": [response]}

    llm = get_llm()
    # Bind tools so the model can request function calls
    try:
        llm_with_tools = llm.bind_tools(TOOL_DEFINITIONS)
        response = llm_with_tools.invoke(state["messages"])
    except Exception as e:
        err_str = str(e)
        # If provider rejects the tool definitions, try without tools
        if "400" in err_str or "BadRequest" in err_str or "tool" in err_str.lower():
            print(f"[Agent] Tool binding rejected by provider ({e.__class__.__name__}), retrying without tools")
            try:
                response = llm.invoke(state["messages"])
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
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        checkpointer = SqliteSaver(conn)

    return workflow.compile(checkpointer=checkpointer)


# Pre-built graph instance
agent_graph = build_agent_graph()