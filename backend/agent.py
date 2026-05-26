"""
Agent Node Definitions — LangGraph ReAct loop nodes.

Defines WorkflowState TypedDict, the call_model and tools_node,
the graph builder function for the E.sapiens v2 agent,
and a tiered query router for fast-pathing simple queries.
"""

import json
import os
import re
import pandas as pd
from enum import Enum
from typing import Annotated, Any, Literal, Sequence, TypedDict

import operator

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from tools import TOOL_DEFINITIONS, execute_tool
from prompts import (
    get_prompt,
    build_skill_context_block,
    build_tool_definitions_block,
    build_output_format_block,
    build_specialist_guidance,
    load_env_description,
    build_env_context_block,
)
from compress import compress_messages, should_compress, count_tokens
from intent_classifier import classify_query
from skill_loader import get_skill_loader, SkillContextBuilder
from pathlib import Path

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
chosen_model = os.getenv("OPENROUTER_MODEL", "inception/mercury-2")


class WorkflowState(TypedDict):
    """State passed between nodes in the ReAct loop."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    query: str
    result: str
    loaded_skills: list[str]
    tool_calls: list[dict[str, Any]]

    # ── Working Memory: Debug Log ──────────────────────────────────────────────
    # Tracks approach history and failure patterns to enable strategy switching.
    # Prevents the agent from repeating the same failing approach indefinitely.
    debug_log: list["DebugEntry"]


class DebugEntry(TypedDict, total=False):
    """Single entry in the working-memory debug log."""

    tool: str  # which tool was called
    approach: str  # short label for what was tried (e.g. "index-22-pam50")
    strategy: str  # overall strategy (e.g. "index_access", "name_search")
    succeeded: bool  # did this approach produce useful output?
    result_preview: str  # first ~120 chars of the result for LLM to review
    failure_reason: str | None  # why it failed (empty output, wrong data, error)
    switch_triggered: bool  # did a strategy switch fire at this entry?


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
    query = state["query"]
    skill_paths = classify_query(query)

    bioskills_path = Path(__file__).parent.parent / "bioSkills"
    loader = get_skill_loader(bioskills_path)
    builder = SkillContextBuilder(loader)
    skills_context = builder.build_context(skill_paths, max_length=6000)

    # Load environment description
    env_description = load_env_description()

    # Build the system message with skill context
    tool_definitions_str = "\n".join(
        f"  - {t['name']}: {t['description']}" for t in TOOL_DEFINITIONS
    )
    system_content = get_prompt(
        "standard",
        env_context_block=build_env_context_block(
            env_description
            if env_description
            else "(environment description not available)"
        ),
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
    has_system = any(
        isinstance(msg, SystemMessage) for msg in state.get("messages", [])
    )
    new_messages: list[BaseMessage] = []
    if not has_system:
        new_messages.append(system_msg)
    new_messages.append(HumanMessage(content=query))

    return {
        "messages": new_messages,
        "loaded_skills": skill_paths,
        "debug_log": [],  # initialize working memory
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
            print(
                f"[Compress] {len(messages)} msgs → {len(compressed)} "
                f"({count_tokens(messages)} → {count_tokens(compressed)} tokens)"
            )
            messages = compressed

    # Bind tools so the model can request function calls
    try:
        llm_with_tools = llm.bind_tools(TOOL_DEFINITIONS)
        response = llm_with_tools.invoke(messages)
    except Exception as e:
        err_str = str(e)
        # If provider rejects the tool definitions, try without tools
        if "400" in err_str or "BadRequest" in err_str or "tool" in err_str.lower():
            print(
                f"[Agent] Tool binding rejected by provider ({e.__class__.__name__}), retrying without tools"
            )
            try:
                response = llm.invoke(messages)
            except Exception as e2:
                print(f"[Agent] LLM invocation failed: {e2}")
                return {
                    "messages": [
                        AIMessage(
                            content="I encountered an error processing your request. Please try again."
                        )
                    ]
                }
        else:
            print(f"[Agent] LLM invocation failed: {e}")
            return {
                "messages": [
                    AIMessage(
                        content="I encountered an error processing your request. Please try again."
                    )
                ]
            }
    return {"messages": [response]}


# ── Node: tools_node ─────────────────────────────────────────────────────────


def _classify_approach(name: str, args: dict, result_str: str) -> tuple[str, str]:
    """Classify the approach/strategy used in a tool call.

    Returns (strategy_label, approach_label).
    strategy = overarching method (index_access, name_search, url_fetch, etc.)
    approach = specific variant tried (index-22, contains-PAM50, tcga-xena-fetch, etc.)
    """
    a = args.get("code", "") or args.get("description", "") or str(args)

    if name == "execute_python":
        if "columns[" in a or "iloc" in a or ".columns[" in a or "col[" in a.lower():
            # Extract the column index if present
            idx_match = re.search(r"columns?\[(\d+)\]|iloc\[.*?(\d+)", a)
            idx = idx_match.group(1) or idx_match.group(2) or "?"
            return ("index_access", f"index-{idx}")
        elif "columns" in a and ("PAM50" in a or "OS_" in a or "Vital" in a):
            return ("name_search", "contains-PAM50-or-survival")
        elif "tcga" in a.lower() or "xena" in a.lower():
            return ("url_fetch", "tcga-xena-url")
        elif "read_csv" in a:
            return ("file_read", "csv-read")
        else:
            return ("execute_python", "generic-code")

    if name in ("run_modal_job", "run_bio_pipeline"):
        return ("modal_dispatch", f"modal-{args.get('job_type', 'generic')}")

    if name == "download_pdb":
        return ("db_fetch", f"pdb-{args.get('pdb_id', '?')}")

    return ("unknown", "generic")


_STRATEGY_SWITCH_THRESHOLD = 3  # switch after 3 consecutive failures of same strategy
_STUCK_PATTERNS = (
    re.compile(
        r"'nan'|value_counts\(\).*dtype|Series\(\[\].*dtype|surv_df.*0\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"len\(df\)\s*==\s*0|Total\s+evaluable\s+samples:\s*0", re.IGNORECASE),
)


def _is_failed_output(result_str: str) -> bool:
    """Return True if result_str looks like a failed/empty-data approach."""
    try:
        d = json.loads(result_str) if result_str.startswith("{") else {}
    except Exception:
        return False
    # Empty dataframe or zero-row result
    data = d.get("data", {})
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and len(v) == 0:
                return True
            if isinstance(v, pd.DataFrame) and len(v) == 0:
                return True
    return bool(
        _STUCK_PATTERNS[0].search(result_str) or _STUCK_PATTERNS[1].search(result_str)
    )


def tools_node(state: WorkflowState) -> dict:
    """
    Execute tool calls requested by the model.
    Returns ToolMessage results appended to the message list.

    Also writes a DebugEntry to state["debug_log"] for every tool call,
    recording approach, strategy, success/failure, and whether a strategy
    switch was triggered.
    """
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {
            "messages": [],
            "tool_calls": [],
            "debug_log": state.get("debug_log", []),
        }

    tool_messages: list[ToolMessage] = []
    tool_calls_record: list[dict] = []
    debug_log: list[DebugEntry] = list(state.get("debug_log", []))

    # Build failure history to detect stuck strategies
    strategy_failures: dict[str, int] = {}
    for entry in debug_log:
        if not entry.get("succeeded") and entry.get("strategy"):
            strategy_failures[entry["strategy"]] = (
                strategy_failures.get(entry["strategy"], 0) + 1
            )

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

        # Write debug entry
        strategy, approach = _classify_approach(name, args, result_str)
        succeeded = not _is_failed_output(result_str)
        failure_reason = None
        switch_triggered = False

        if not succeeded:
            strategy_failures[strategy] = strategy_failures.get(strategy, 0) + 1
            if strategy_failures[strategy] >= _STRATEGY_SWITCH_THRESHOLD:
                failure_reason = f"strategy_{strategy}_exceeded_threshold"
                switch_triggered = True
                strategy_failures[strategy] = 0  # reset after switch
        else:
            # Success — reset failure count for this strategy
            strategy_failures.pop(strategy, None)

        try:
            preview = result_str[:150] if result_str else ""
        except Exception:
            preview = result_str[:150] if result_str else ""

        entry: DebugEntry = {
            "tool": name,
            "approach": approach,
            "strategy": strategy,
            "succeeded": succeeded,
            "result_preview": preview,
            "failure_reason": failure_reason,
            "switch_triggered": switch_triggered,
        }
        debug_log.append(entry)

    return {
        "messages": tool_messages,
        "tool_calls": tool_calls_record,
        "debug_log": debug_log,
    }


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


# ── Node: critic_node (Working Memory — Strategy Switcher) ───────────────────


_CRITIC_SYSTEM_PROMPT = """You are E.sapiens's built-in critic. Your ONLY job is to detect when
the agent is stuck in a loop and force a strategy switch.

EVALUATION CRITERIA — check the debug_log entries:
1. Has the same strategy failed 3+ times consecutively? (same approach, no progress)
2. Is the result empty, all-nan, or zero-row despite multiple attempts?
3. Did an index-based column access return the wrong column (e.g. PAM50 col returned RPPA_Clusters)?

If ANY of the above is true → STRATEGY SWITCH REQUIRED.

When you detect a stuck pattern, output this exact format (MUST be followed exactly):

[STRATEGY SWITCH]
reason: <one line why it's stuck>
old_strategy: <the failing strategy>
new_strategy: <what to switch to>
directive: <specific instruction on what the agent must do differently on the NEXT call_model turn>
[/STRATEGY SWITCH]

If NOT stuck → output nothing (empty string)."""


def _build_critic_message(state: WorkflowState) -> str | None:
    """Return a strategy-switch message if a switch was triggered, else None."""
    debug_log: list[DebugEntry] = state.get("debug_log", [])
    if not debug_log:
        return None

    # Check if any entry in this round triggered a switch
    recent = debug_log[-3:]  # only look at last 3 entries (current round)
    triggered = [e for e in recent if e.get("switch_triggered")]
    if not triggered:
        return None

    # Build context for the critic
    entries_text = "\n".join(
        f"[{i}] tool={e.get('tool','?')} strategy={e.get('strategy','?')} "
        f"succeeded={e.get('succeeded')} approach={e.get('approach','?')} "
        f"preview={e.get('result_preview','?')[:100]}"
        for i, e in enumerate(debug_log[-8:])  # last 8 entries for context
    )

    # Include last tool result to help critic understand what went wrong
    last_tc = state.get("tool_calls", [])
    last_result = last_tc[-1].get("result", "")[:500] if last_tc else "N/A"

    prompt = f"""Debug log (last 8 entries):
{entries_text}

Last tool result (raw):
{last_result}

{_CRITIC_SYSTEM_PROMPT}"""

    # Call the LLM directly for the critic decision
    # Use a fast, cheap model for the critic
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or key.startswith("sk-or-v1-placeholder"):
        return None

    try:
        from langchain_openai import ChatOpenAI

        critic_llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            model=os.getenv("OPENROUTER_MODEL", "inception/mercury-2"),
            temperature=0.0,
            max_completion_tokens=512,
            timeout=30,
        )
        response = critic_llm.invoke(
            [
                {
                    "role": "system",
                    "content": "You are a strict critic. Only output a strategy switch block if the agent is clearly stuck. Otherwise output nothing.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        raw = response.content if hasattr(response, "content") else str(response)
        # content can be str | list[dict] — normalize to str
        content = (
            raw
            if isinstance(raw, str)
            else str(raw[0]) if isinstance(raw, list) and raw else ""
        )
        if content and "[STRATEGY SWITCH]" in content:
            return content
    except Exception as e:
        print(f"[Critic] LLM call failed: {e}")
    return None


def critic_node(state: WorkflowState) -> dict:
    """
    Working-memory critic node.
    Evaluates the debug_log; if a strategy switch was triggered, injects
    a forced strategy-switch directive into the message list so the next
    call_model turn receives it as a new HumanMessage.
    """
    switch_msg = _build_critic_message(state)
    if not switch_msg:
        return {"messages": []}

    # Inject the switch directive as a new HumanMessage — forces the next
    # call_model to process the switch instruction before its own reasoning
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content=f"[WORKING MEMORY CRITIC]\n{switch_msg}")]
    }


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
    workflow.add_node("critic_node", critic_node)
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
    workflow.add_edge("tools_node", "critic_node")
    workflow.add_edge("critic_node", "call_model")
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
