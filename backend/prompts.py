"""
E.sapiens Prompt Library — Centralized prompt management.

All LLM system prompts live in prompts.json. Load via get_prompt(name).

Usage:
    from prompts import get_prompt, get_model_config, get_style_rules

    # Get a plain prompt (identity-only)
    content = get_prompt("direct")

    # Get a prompt with block substitution
    content = get_prompt(
        "standard",
        skill_context_block="## Skill: sequence-io\n\n...",
        tool_definitions_block="  - download_pdb: Download a PDB...",
        specialist_guidance="Follow the standard analysis protocol...",
    )

    # Get model config for a prompt
    config = get_model_config("standard")
    # Returns {"temperature": 0.0, "max_tokens": 4096, ...}

    # Get style rules
    rules = get_style_rules()

Prompt tiers:
  identity     — Core persona, injected into ALL prompts
  direct       — Greetings, meta-questions (no tools, fast path)
  standard     — Standard bio queries (full ReAct loop, skill context)
  heavy        — Multi-step pipelines (extended loop, Modal dispatch)
  domain/*     — Domain-specific analysis protocols (protein_structure,
                 sequence_analysis, variant_analysis, transcriptomics,
                 literature_research, data_visualization)
  system/*     — System-level fragments (modal_execution, error)
  mock_response — Fallback when no API key configured
"""

import json
from pathlib import Path
from typing import Any, Optional

# ── Loader ────────────────────────────────────────────────────────────────────

_PROMPTS_PATH = Path(__file__).parent / "prompts.json"

_cached: Optional[dict] = None


def _load() -> dict:
    global _cached
    if _cached is None:
        _cached = json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))
    return _cached


# ── Public API ────────────────────────────────────────────────────────────────


def get_prompt(
    name: str,
    /,
    # Block substitution — these are injected only if the placeholder
    # exists in the prompt template (conditional substitution).
    identity: Optional[str] = None,
    env_context_block: Optional[str] = None,
    skill_context_block: Optional[str] = None,
    tool_definitions_block: Optional[str] = None,
    specialist_guidance: Optional[str] = None,
    # Legacy / mock substitutions
    query: Optional[str] = None,
    tool_names: Optional[str] = None,
    **extra: str,
) -> str:
    """
    Return the prompt content for the given name.

    Conditional block substitution: if a placeholder like {skill_context_block}
    exists in the prompt template AND the corresponding kwarg is provided,
    it is replaced with the block wrapped in its header/footer.

    If the placeholder is absent from the template, the kwarg is silently
    ignored — so get_prompt() is safe to call with any combination of kwargs.

    Variables:
      identity              → replaced verbatim (identity prompt text)
      skill_context_block   → wrapped in "## Relevant Skill Context..." block
      tool_definitions_block → wrapped in "## Available Tools" block
      specialist_guidance   → replaced verbatim
      query                 → for mock_response placeholder
      tool_names             → for mock_response placeholder
    """
    data = _load()
    prompt_obj = data["prompts"].get(name)

    if prompt_obj is None:
        available = list(data["prompts"].keys())
        raise KeyError(f"Unknown prompt: '{name}'. Available: {available}")

    content = prompt_obj["content"]

    # Resolve identity — always load from the identity prompt if not provided
    if identity is None and "{identity}" in content:
        identity = get_prompt("identity")

    # Build the substitution dict from what was actually provided
    subs: dict[str, str] = {}
    for key, value in [
        ("identity", identity),
        ("env_context_block", env_context_block),
        ("skill_context_block", skill_context_block),
        ("tool_definitions_block", tool_definitions_block),
        ("specialist_guidance", specialist_guidance),
        ("query", query),
        ("tool_names", tool_names),
    ]:
        if value is not None and f"{{{key}}}" in content:
            subs[key] = value

    # Extra catch-all for any additional variables
    for k, v in extra.items():
        if f"{{{k}}}" in content:
            subs[k] = v

    return content.format(**subs)


def get_prompt_meta(name: str) -> dict[str, Any]:
    """Return the full metadata for a prompt (description, model_config, etc.)."""
    data = _load()
    obj = data["prompts"].get(name)
    if obj is None:
        raise KeyError(f"Unknown prompt: '{name}'")
    return {
        "name": obj["name"],
        "description": obj["description"],
        "model_config": obj.get("model_config", {}),
    }


def get_model_config(name: str) -> dict[str, Any]:
    """Return the model config (temperature, max_tokens, model_override_env) for a prompt."""
    return get_prompt_meta(name)["model_config"]


def get_style_rules() -> dict[str, Any]:
    """Return the global style rules."""
    data = _load()
    return data.get("style_rules", {})


def get_model_config_for_tier(tier: str) -> dict[str, Any]:
    """Return the effective model config for a query tier string."""
    data = _load()
    mc = data.get("model_config", {}).copy()
    t = tier.lower()
    if t == "direct":
        mc.setdefault("temperature", 0.3)
        mc.setdefault("max_tokens", 1024)
    elif t == "heavy":
        mc.setdefault("temperature", 0.0)
        mc.setdefault("max_tokens", 8192)
    else:
        mc.setdefault("temperature", 0.0)
        mc.setdefault("max_tokens", 4096)
    return mc


def get_identity_prompt() -> str:
    """Return the raw identity prompt text."""
    return get_prompt("identity")


def list_prompts() -> list[str]:
    """Return all available prompt names."""
    return list(_load()["prompts"].keys())


def reload() -> None:
    """Force-reload prompts.json (useful after editing prompts.json)."""
    global _cached
    _cached = None
    _load()


# ── Block builders ─────────────────────────────────────────────────────────────
# These are used to wrap tool_definitions and skill_context in standard headers.
# Called automatically by get_prompt() when the corresponding placeholder
# exists in the template.


def build_skill_context_block(skill_context: str, max_length: int = 6000) -> str:
    """
    Wrap a skill context string in the standard block header.
    Truncates to max_length characters.
    """
    header = "## Relevant Skill Context (dynamically loaded from bioSkills/)\n\n"
    footer = "\n\n[Skill context end]"
    available = max_length - len(header) - len(footer) - 10
    if len(skill_context) > available:
        skill_context = (
            skill_context[:available] + "\n\n[... skill context truncated ...]"
        )
    return header + skill_context + footer


def build_tool_definitions_block(tool_definitions: str) -> str:
    """Wrap tool definitions string in the standard block header."""
    header = "## Available Tools\n\nYou may call the following tools. Always verify arguments before calling. If a needed capability is absent, use create_tool() to build it.\n\n"
    return header + tool_definitions


def build_output_format_block() -> str:
    """Return the output format rules block for rendering compliance."""
    data = _load()
    block = data.get("prompt_blocks", {}).get("output_format_block", "")
    return block


def build_specialist_guidance(prompt_name: str) -> str:
    """Return the specialist guidance text for a prompt name."""
    data = _load()
    block = data.get("prompt_blocks", {}).get("specialist_guidance", "")
    return block.format(specialist_guidance=block)


def build_env_context_block(env_context: str, max_length: int = 2000) -> str:
    """Wrap environment context string in the standard block header.

    Truncates to max_length characters if needed.
    """
    header = "## Environment Awareness\n\n"
    footer = "\n\n[Environment context end]"
    available = max_length - len(header) - len(footer) - 10
    if len(env_context) > available:
        env_context = (
            env_context[:available] + "\n\n[... environment context truncated ...]"
        )
    return header + env_context + footer


def load_env_description() -> str:
    """Load the environment self-description from the markdown file.

    Returns the file content, or a fallback string if the file is missing.
    """
    from pathlib import Path

    env_file = Path(__file__).parent / "E.SAPIENS_ENVIRONMENT.md"
    if env_file.exists():
        return env_file.read_text(encoding="utf-8")
    return "(Environment description not available — file missing.)"
