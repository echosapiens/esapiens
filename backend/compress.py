"""
E.sapiens Context Compression Module
═══════════════════════════════════════

Prevents token overflow by compressing conversation history before LLM
invocation. Two strategies:

  1. PRUNE — Drop oldest messages, keeping the system prompt + last N messages.
     Fast, deterministic, zero LLM cost. Used when context is mildly over limit.

  2. SUMMARIZE — Use a fast/cheap model to compress older messages into a
     compact summary, preserving key facts and decisions. Used when pruning
     alone would lose too much context.

Compression triggers when estimated token count exceeds a configurable
threshold (default: 80% of model context window). The module uses tiktoken
for accurate counting when available, falling back to a 4-chars-per-token
estimate.

Architecture:
  compress_messages() is called from agent.py's call_model node BEFORE
  invoking the LLM. It operates on the WorkflowState.messages list and
  returns a compressed list that fits within the budget.

  The compression summary is injected as a SystemMessage tagged with a
  special marker so downstream code can distinguish it from the original
  system prompt.
"""

import os
import logging
from typing import Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

# ── Token estimation ────────────────────────────────────────────────────────

try:
    import tiktoken

    _ENC = tiktoken.encoding_for_model("gpt-4o")
    _TICKTOK_AVAILABLE = True
except Exception:
    _ENC = None
    _TICKTOK_AVAILABLE = False


def count_tokens(messages: list[BaseMessage]) -> int:
    """Estimate total tokens for a list of LangChain messages.

    Uses tiktoken when available for accuracy, falls back to 4 chars/token.
    """
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        # Always use tiktoken if available — it handles all model families well enough
        if _TICKTOK_AVAILABLE and _ENC is not None:
            total += len(_ENC.encode(content))
        else:
            total += max(1, len(content) // 4)
        # Tool calls have extra token overhead
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                total += (
                    len(_ENC.encode(str(tc)))
                    if (_TICKTOK_AVAILABLE and _ENC)
                    else max(1, len(str(tc)) // 4)
                )
        if isinstance(msg, ToolMessage):
            total += 4  # Tool message metadata overhead
    return total


def _count_message_tokens(msg: BaseMessage) -> int:
    """Estimate tokens for a single message."""
    return count_tokens([msg])


# ── Configuration ─────────────────────────────────────────────────────────────

# Default context window sizes (tokens)
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # OpenRouter models — use the largest known context as default
    "default": 128_000,
    "deepseek/deepseek-chat": 128_000,
    "arcee-ai/trinity-large-thinking": 128_000,
    "openai/gpt-4o": 128_000,
    "openai/gpt-4o-mini": 128_000,
    "anthropic/claude-sonnet-4": 200_000,
    "google/gemini-2.5-pro": 1_048_576,
}

# Fraction of context window to use before compression kicks in
COMPRESSION_THRESHOLD = 0.80

# Minimum number of recent messages to always preserve (never compress)
MIN_RECENT_MESSAGES = 4  # Last 2 exchanges (2 human + 2 AI)

# Maximum tokens for the compression summary itself
MAX_SUMMARY_TOKENS = 2_000

# Marker for compressed summary messages (so we can replace them on re-compress)
COMPRESSION_MARKER = "[E.sapiens Context Summary]"


# ── Compression functions ──────────────────────────────────────────────────────


def get_context_window(model_name: str) -> int:
    """Get the context window size for a model, with env override."""
    env_override = os.environ.get("ESAPIENS_CONTEXT_WINDOW")
    if env_override:
        try:
            return int(env_override)
        except ValueError:
            pass
    # Try exact match, then prefix match, then default
    for key, window in MODEL_CONTEXT_WINDOWS.items():
        if model_name == key:
            return window
    for key, window in MODEL_CONTEXT_WINDOWS.items():
        if (
            model_name.startswith(key.split("/")[0])
            if "/" in key
            else model_name == key
        ):
            return window
    return MODEL_CONTEXT_WINDOWS["default"]


def should_compress(messages: list[BaseMessage], model_name: str) -> bool:
    """Return True if the message list exceeds the compression threshold."""
    context_window = get_context_window(model_name)
    threshold = int(context_window * COMPRESSION_THRESHOLD)
    token_count = count_tokens(messages)
    if token_count > threshold:
        logger.info(
            f"[Compress] Token count {token_count} exceeds threshold {threshold} "
            f"({context_window} window x {COMPRESSION_THRESHOLD:.0%}). Compressing."
        )
        return True
    return False


def compress_messages(
    messages: list[BaseMessage],
    model_name: str,
    openrouter_api_key: Optional[str] = None,
) -> list[BaseMessage]:
    """Compress a message list to fit within the model's context window.

    Strategy:
      1. Separate system prompt (never compress)
      2. Remove any prior compression summaries (replace with fresh one)
      3. Try PRUNE: drop oldest messages, keep recent ones
      4. If pruning loses too much context (would drop >50% of messages),
         use SUMMARIZE instead: compress older messages into a summary

    Returns a new list of messages that fits within the context budget.
    """
    context_window = get_context_window(model_name)
    max_tokens = int(context_window * COMPRESSION_THRESHOLD)

    if not should_compress(messages, model_name):
        return messages

    # Step 1: Separate system prompt from conversation
    system_msgs: list[BaseMessage] = []
    conv_msgs: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, SystemMessage) and COMPRESSION_MARKER not in (
            msg.content or ""
        ):
            system_msgs.append(msg)
        else:
            conv_msgs.append(msg)

    system_tokens = count_tokens(system_msgs)
    budget = (
        max_tokens - system_tokens - MAX_SUMMARY_TOKENS - 200
    )  # 200 token safety margin

    if budget < 1000:
        # Even with aggressive compression, barely fits. Just keep system + last 2 exchanges.
        logger.warning(
            "[Compress] Extremely tight budget. Keeping only last 2 exchanges."
        )
        recent = conv_msgs[-(MIN_RECENT_MESSAGES * 2) :]  # last N messages
        summary = _build_truncation_summary(conv_msgs[: -(MIN_RECENT_MESSAGES * 2)])
        return system_msgs + ([summary] if summary else []) + recent

    # Step 2: Remove any prior compression summaries from conv_msgs
    conv_msgs = [
        m
        for m in conv_msgs
        if not (
            isinstance(m, SystemMessage) and COMPRESSION_MARKER in (m.content or "")
        )
    ]

    # Step 3: Estimate if simple pruning is sufficient
    #  Keep the most recent messages that fit within budget
    recent_tokens = 0
    keep_from_end = 0
    for i, msg in enumerate(reversed(conv_msgs)):
        msg_tokens = _count_message_tokens(msg)
        if recent_tokens + msg_tokens > budget / 2:
            # Stop keeping from the end — we'd lose too much
            break
        recent_tokens += msg_tokens
        keep_from_end += 1

    # If we can keep > 50% of messages via simple pruning, just prune
    if keep_from_end >= len(conv_msgs) * 0.5:
        logger.info(
            f"[Compress] Pruning: keeping {keep_from_end}/{len(conv_msgs)} recent messages."
        )
        pruned = (
            conv_msgs[-keep_from_end:]
            if keep_from_end > 0
            else conv_msgs[-MIN_RECENT_MESSAGES:]
        )
        summary = _build_truncation_summary(
            conv_msgs[:-keep_from_end] if keep_from_end < len(conv_msgs) else []
        )
        return system_msgs + ([summary] if summary else []) + pruned

    # Step 4: Summarize older messages using LLM
    logger.info(
        f"[Compress] Summarizing: {len(conv_msgs) - keep_from_end} older messages, "
        f"keeping {keep_from_end} recent."
    )
    older_msgs = (
        conv_msgs[:-keep_from_end]
        if keep_from_end > 0
        else conv_msgs[:-MIN_RECENT_MESSAGES]
    )
    recent_msgs = (
        conv_msgs[-keep_from_end:]
        if keep_from_end > 0
        else conv_msgs[-MIN_RECENT_MESSAGES:]
    )

    summary = _summarize_with_llm(older_msgs, openrouter_api_key, model_name)
    if summary:
        summary_msg = SystemMessage(content=f"{COMPRESSION_MARKER}\n\n{summary}")
    else:
        # LLM summarize failed — fall back to truncation summary
        summary_msg = _build_truncation_summary(older_msgs)

    result = system_msgs + ([summary_msg] if summary_msg else []) + recent_msgs

    # Verify we're within budget
    final_tokens = count_tokens(result)
    if final_tokens > max_tokens:
        # Still over — aggressively trim the recent messages
        logger.warning(
            f"[Compress] Still over budget after summarize ({final_tokens}/{max_tokens}). "
            "Falling back to aggressive prune."
        )
        while final_tokens > max_tokens and len(recent_msgs) > MIN_RECENT_MESSAGES:
            recent_msgs = recent_msgs[1:]  # drop oldest of recent
            result = system_msgs + ([summary_msg] if summary_msg else []) + recent_msgs
            final_tokens = count_tokens(result)

    return result


def _build_truncation_summary(messages: list[BaseMessage]) -> Optional[SystemMessage]:
    """Build a brief summary from messages being truncated.

    Extracts key facts from older messages without LLM calls.
    Returns a SystemMessage with the summary, or None if nothing to summarize.
    """
    if not messages:
        return None

    # Collect key pieces of information
    topics: list[str] = []
    tools_used: list[str] = []
    decisions: list[str] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Extract first sentence as topic
            first_sentence = content.split(".")[0].split("\n")[0][:120]
            if first_sentence.strip():
                topics.append(first_sentence.strip())
        elif isinstance(msg, AIMessage):
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append(tc.get("name", "unknown"))
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Look for decision-like sentences
            for line in content.split("\n"):
                line = line.strip()
                if any(
                    kw in line.lower()
                    for kw in ["decided", "chose", "selected", "concluded", "result:"]
                ):
                    decisions.append(line[:150])
        elif isinstance(msg, ToolMessage):
            # Note tool usage without repeating content
            pass

    if not topics and not tools_used:
        return None

    # Build compact summary
    parts = [COMPRESSION_MARKER, ""]
    if topics:
        parts.append("Previous conversation topics:")
        # Keep last 8 topics max
        for t in topics[-8:]:
            parts.append(f"  - {t}")
    if tools_used:
        unique_tools = list(dict.fromkeys(tools_used))  # dedupe preserving order
        parts.append(f"Tools previously used: {', '.join(unique_tools[:12])}")
    if decisions:
        parts.append("Key decisions made:")
        for d in decisions[-4:]:
            parts.append(f"  - {d}")

    return SystemMessage(content="\n".join(parts))


def _summarize_with_llm(
    messages: list[BaseMessage],
    api_key: Optional[str],
    model_name: str,
) -> Optional[str]:
    """Use a fast/cheap model to summarize older conversation messages.

    Falls back to None if the LLM call fails, triggering truncation summary instead.
    """
    if not messages:
        return None

    # Use a fast cheap model for summarization, not the main model
    summarize_model = os.environ.get("ESAPIENS_SUMMARIZE_MODEL", "arcee-ai/trinity-large-thinking")
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key or key.startswith("sk-or-v1-placeholder"):
        return None

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
            model=summarize_model,
            temperature=0.0,
            max_tokens=MAX_SUMMARY_TOKENS,
            timeout=30,
            default_headers={
                "HTTP-Referer": "https://echosapiens.bio",
                "X-Title": "E.sapiens Context Compressor",
            },
        )

        # Build a compact representation of the messages for summarization
        convo_lines = []
        for msg in messages:
            if isinstance(msg, SystemMessage) and COMPRESSION_MARKER in (
                msg.content or ""
            ):
                continue  # Skip old summaries
            role = (
                "user"
                if isinstance(msg, HumanMessage)
                else (
                    "assistant"
                    if isinstance(msg, AIMessage)
                    else "tool" if isinstance(msg, ToolMessage) else "system"
                )
            )
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Truncate very long tool/tool result messages
            if len(content) > 2000:
                content = content[:2000] + "...[truncated]"
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_names = [tc.get("name", "?") for tc in msg.tool_calls]
                convo_lines.append(f"{role}: [called tools: {', '.join(tool_names)}]")
                if content.strip():
                    convo_lines.append(f"assistant: {content[:500]}")
            else:
                convo_lines.append(f"{role}: {content}")
            if len(convo_lines) > 60:
                convo_lines.append("...[remaining messages truncated]")
                break

        convo_text = "\n".join(convo_lines)

        summary_prompt = (
            "Summarize this conversation history compactly. "
            "Preserve: key topics discussed, tools used, important results/decisions, "
            "file paths mentioned, data identifiers (gene names, accession numbers), "
            "and any conclusions reached. Be factual and concise (under 800 words). "
            "Use bullet points.\n\n"
            f"CONVERSATION:\n{convo_text}"
        )

        response = llm.invoke([HumanMessage(content=summary_prompt)])
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        return content if isinstance(content, str) and content.strip() else None

    except Exception as e:
        logger.warning(
            f"[Compress] LLM summarization failed: {e}. Falling back to truncation."
        )
        return None
