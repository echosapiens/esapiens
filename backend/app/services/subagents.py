"""Subagent registry for the Supervisor architecture.

Each subagent is a tool the Supervisor can invoke. Workers do NOT
communicate with each other — they only report back to the Supervisor.

Available subagents:
  - biology: genomics, proteomics, literature interpretation
  - math:    statistical tests, Bayesian modeling, effect sizes
  - code:    Python scripting, pipeline construction, data wrangling
  - literature: paper search, citation extraction, summarization

Each subagent is a thin wrapper around an LLM call with a specialized
system prompt. Returns a structured SubagentResult for the Supervisor
to synthesize.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.services.llm import get_llm

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────────


class SubagentRole(str, Enum):
    """Roles a subagent can fulfill. Supervisor picks one per delegation."""

    BIOLOGY = "biology"
    MATH = "math"
    CODE = "code"
    LITERATURE = "literature"


class SubagentResult(BaseModel):
    """Structured output from a subagent call.

    The Supervisor reads this to decide what to do next.
    """

    role: SubagentRole
    task: str = Field(..., description="The specific task the subagent was given")
    findings: str = Field(..., description="Natural-language summary of findings")
    structured_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Machine-readable findings (genes, p-values, code, citations, etc.)",
    )
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Self-assessed confidence 0-1"
    )
    citations: list[str] = Field(
        default_factory=list, description="DOIs, paper titles, or source references"
    )
    tool_call_id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── System prompts per subagent ──────────────────────────────────────────

_BIOLOGY_SYSTEM = """You are a biology subagent within the E.sapiens multi-agent system.

You specialize in molecular biology, genomics, proteomics, and bioinformatics interpretation.
You receive a focused question from the Supervisor and return a structured analysis.

Your response MUST be valid JSON matching this schema:
{
  "findings": "Natural-language answer (2-4 sentences)",
  "structured_data": {
    "genes": ["list of gene symbols mentioned"],
    "organisms": ["list of organisms/species"],
    "databases": ["relevant DBs: NCBI, UniProt, Ensembl, etc."],
    "techniques": ["experimental methods: WGS, RNA-seq, ChIP-seq, etc."]
  },
  "confidence": 0.0-1.0,
  "citations": ["PMID:12345 or DOI:10.xxx/yyy or paper title"]
}

Be precise. If you don't know, set confidence below 0.5 and explain in findings."""


_MATH_SYSTEM = """You are a statistics and modeling subagent within the E.sapiens multi-agent system.

You specialize in statistical tests, Bayesian inference, effect sizes, and experimental design.
You receive a focused statistical question from the Supervisor and return a structured analysis.

Your response MUST be valid JSON matching this schema:
{
  "findings": "Natural-language answer (2-4 sentences)",
  "structured_data": {
    "test_name": "name of statistical test, e.g. 'Welch t-test'",
    "p_value": null or number,
    "effect_size": null or number,
    "assumptions": ["normality", "independence", etc.],
    "sample_size_recommendation": "power analysis result"
  },
  "confidence": 0.0-1.0,
  "citations": ["DOI:10.xxx/yyy"]
}"""


_CODE_SYSTEM = """You are a code subagent within the E.sapiens multi-agent system.

You specialize in Python, bioinformatics pipelines, data wrangling, and shell scripting.
You receive a focused implementation question from the Supervisor and return structured code.

Your response MUST be valid JSON matching this schema:
{
  "findings": "Natural-language explanation (2-4 sentences)",
  "structured_data": {
    "language": "python" | "bash" | "r" | "sql",
    "code": "the actual code as a string",
    "dependencies": ["list of pip/cran packages needed"],
    "estimated_runtime_seconds": 0
  },
  "confidence": 0.0-1.0,
  "citations": ["URL to documentation"]
}"""


_LITERATURE_SYSTEM = """You are a literature subagent within the E.sapiens multi-agent system.

You specialize in searching and summarizing scientific literature, extracting citations,
and contextualizing findings within the published evidence base.

Your response MUST be valid JSON matching this schema:
{
  "findings": "Natural-language summary of literature (2-4 sentences)",
  "structured_data": {
    "paper_count": 0,
    "key_papers": [
      {"title": "...", "authors": "...", "year": 2024, "journal": "..."}
    ],
    "consensus": "what the literature broadly agrees on",
    "controversies": "open questions or conflicting findings"
  },
  "confidence": 0.0-1.0,
  "citations": ["DOI:10.xxx/yyy", "PMID:12345"]
}"""


_SYSTEM_PROMPTS: dict[SubagentRole, str] = {
    SubagentRole.BIOLOGY: _BIOLOGY_SYSTEM,
    SubagentRole.MATH: _MATH_SYSTEM,
    SubagentRole.CODE: _CODE_SYSTEM,
    SubagentRole.LITERATURE: _LITERATURE_SYSTEM,
}


# ── Subagent invocation ──────────────────────────────────────────────────


async def invoke_subagent(
    role: SubagentRole,
    task: str,
    context: str = "",
    timeout: float = 15.0,
) -> SubagentResult:
    """Invoke a specialized subagent and return structured findings.

    Each subagent is a single LLM call with a role-specific system prompt.
    The LLM is forced to return JSON matching SubagentResult.
    """
    import asyncio

    llm = get_llm()
    if llm is None:
        # No LLM available — return a deterministic stub
        return SubagentResult(
            role=role,
            task=task,
            findings=f"[{role.value} subagent unavailable — LLM not configured]",
            structured_data={},
            confidence=0.0,
            citations=[],
        )

    system_prompt = _SYSTEM_PROMPTS[role]
    user_msg = task if not context else f"Context:\n{context}\n\nTask:\n{task}"

    try:
        # Use structured output to force JSON schema compliance
        structured_llm = llm.with_structured_output(SubagentResult)
        result = await asyncio.wait_for(
            structured_llm.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ]
            ),
            timeout=timeout,
        )
        # Ensure role matches what we asked for (LLM may not set it correctly)
        result.role = role
        result.task = task
        logger.info(
            "Subagent %s completed task '%s' (confidence=%.2f)",
            role.value,
            task[:60],
            result.confidence,
        )
        return result
    except Exception as exc:
        logger.warning("Subagent %s failed: %s", role.value, exc)
        return SubagentResult(
            role=role,
            task=task,
            findings=f"[{role.value} subagent error: {exc}]",
            structured_data={"error": str(exc)},
            confidence=0.0,
            citations=[],
        )


# ── LangChain tool wrappers (for Supervisor tool-calling) ────────────────

# LangChain tool-calling requires tools as BaseTool instances or callables
# with type hints. We provide a function-calling interface that the
# Supervisor binds to its LLM.

try:
    from langchain_core.tools import tool as _lc_tool

    @_lc_tool
    async def biology_agent(task: str, context: str = "") -> str:
        """Delegate a biology question to the biology subagent.

        Use for: gene function, pathway analysis, organism-specific facts,
        experimental design in molecular biology, interpretation of genomic
        or proteomic results.

        Args:
            task: A focused question for the biology subagent.
            context: Optional prior findings to ground the subagent's answer.
        """
        result = await invoke_subagent(SubagentRole.BIOLOGY, task, context)
        return result.model_dump_json()

    @_lc_tool
    async def math_agent(task: str, context: str = "") -> str:
        """Delegate a statistics or modeling question to the math subagent.

        Use for: choosing a statistical test, power analysis, effect size
        estimation, Bayesian model specification, multiple-testing correction.
        """
        result = await invoke_subagent(SubagentRole.MATH, task, context)
        return result.model_dump_json()

    @_lc_tool
    async def code_agent(task: str, context: str = "") -> str:
        """Delegate a code or pipeline-implementation question to the code subagent.

        Use for: writing Python/bash, constructing bioinformatics pipelines,
        data wrangling, API calls, database queries.
        """
        result = await invoke_subagent(SubagentRole.CODE, task, context)
        return result.model_dump_json()

    @_lc_tool
    async def literature_agent(task: str, context: str = "") -> str:
        """Delegate a literature search question to the literature subagent.

        Use for: finding relevant papers, extracting citations, summarizing
        the state of evidence on a topic, identifying controversies.
        """
        result = await invoke_subagent(SubagentRole.LITERATURE, task, context)
        return result.model_dump_json()

    # The full set of subagent tools the Supervisor can bind
    SUBAGENT_TOOLS = [
        biology_agent,
        math_agent,
        code_agent,
        literature_agent,
    ]

except ImportError:
    # langchain_core not available — provide stubs so import doesn't break
    logger.warning("langchain_core.tools not available — subagent tools disabled")
    SUBAGENT_TOOLS = []
    biology_agent = None  # type: ignore
    math_agent = None  # type: ignore
    code_agent = None  # type: ignore
    literature_agent = None  # type: ignore


# ── Synthesis ────────────────────────────────────────────────────────────


SUPERVISOR_SYNTHESIS_PROMPT = """You are the Supervisor of the E.sapiens multi-agent system.

You have received findings from one or more subagents (biology, math, code, literature).
Your job is to synthesize a final answer for the user.

Original user question: {original_prompt}

Subagent findings:
{subagent_findings}

Compose a clear, concise answer that:
1. Directly addresses the user's question
2. Integrates relevant findings from subagents
3. Cites sources where appropriate
4. Is honest about uncertainty

Return plain text (not JSON) — this is the final answer the user will see."""


async def synthesize_findings(
    original_prompt: str,
    subagent_results: list[SubagentResult],
    timeout: float = 20.0,
) -> str:
    """Synthesize subagent findings into a final user-facing answer.

    Called by the Supervisor after it has finished delegating to subagents.
    """
    import asyncio

    if not subagent_results:
        return "I wasn't able to gather enough information to answer your question."

    llm = get_llm()
    if llm is None:
        # Deterministic fallback: concatenate findings
        parts = []
        for r in subagent_results:
            parts.append(f"[{r.role.value}] {r.findings}")
        return "\n\n".join(parts)

    findings_text = "\n\n".join(
        f"[{r.role.value}] (confidence={r.confidence:.2f})\n{r.findings}"
        + (f"\nStructured: {json.dumps(r.structured_data, default=str)[:500]}" if r.structured_data else "")
        for r in subagent_results
    )

    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        prompt = SUPERVISOR_SYNTHESIS_PROMPT.format(
            original_prompt=original_prompt,
            subagent_findings=findings_text,
        )
        response = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content="Synthesize the final answer."),
                ]
            ),
            timeout=timeout,
        )
        return response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.warning("Synthesis failed: %s — using concatenation fallback", exc)
        parts = [f"[{r.role.value}] {r.findings}" for r in subagent_results]
        return "\n\n".join(parts)