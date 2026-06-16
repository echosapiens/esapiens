"""Subagent registry for the Supervisor architecture.

Each subagent is a tool the Supervisor can invoke. Workers do NOT
communicate with each other — they only report back to the Supervisor.

Available subagents:
  - biology: genomics, proteomics, literature interpretation
  - math:    statistical tests, Bayesian modeling, effect sizes
  - code:    Python scripting, pipeline construction, data wrangling.
             The code subagent actually EXECUTES code in a Modal Sandbox
             and returns real output (not predicted output).
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
    timeout: float = 300.0,
) -> SubagentResult:
    """Invoke a specialized subagent and return structured findings.

    Each subagent is a single LLM call with a role-specific system prompt.
    The LLM response is parsed as JSON with permissive fallbacks.
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
        # Robust approach: plain text completion, then parse JSON.
        # `with_structured_output(SubagentResult)` is fragile across OpenRouter
        # providers — the model sometimes returns non-conforming JSON or
        # the provider strips the tool_calls. We use a plain prompt and
        # extract the JSON ourselves, with a permissive fallback.
        from langchain_core.messages import SystemMessage, HumanMessage
        import json as _json
        import re as _re

        raw = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=system_prompt + "\n\nIMPORTANT: Respond with valid JSON only. No prose, no markdown fences. The JSON must have keys: findings (string), structured_data (object), confidence (number 0-1), citations (array of strings)."),
                    HumanMessage(content=user_msg),
                ]
            ),
            timeout=timeout,
        )
        content = raw.content if hasattr(raw, "content") else str(raw)
        if not isinstance(content, str):
            content = str(content)

        # Extract JSON from the response — try direct parse, then look for
        # the first { ... } block, then strip markdown fences.
        result: SubagentResult | None = None
        json_match = _re.search(r"\{[\s\S]*\}", content)
        candidates = [content.strip()]
        if json_match:
            candidates.append(json_match.group(0))
        for candidate in candidates:
            if not candidate:
                continue
            try:
                data = _json.loads(candidate)
                # Coerce types
                if "structured_data" not in data or not isinstance(data["structured_data"], dict):
                    data["structured_data"] = {}
                if "confidence" not in data:
                    data["confidence"] = 0.7
                if "citations" not in data or not isinstance(data["citations"], list):
                    data["citations"] = []
                if "findings" not in data:
                    # If no findings key, use the whole content
                    data["findings"] = content[:2000]
                result = SubagentResult(
                    role=role,
                    task=task,
                    findings=str(data.get("findings", ""))[:4000],
                    structured_data=data.get("structured_data", {}),
                    confidence=float(data.get("confidence", 0.7)),
                    citations=[str(c) for c in data.get("citations", [])][:20],
                )
                break
            except Exception:
                continue

        if result is None:
            # Couldn't parse JSON — treat the raw content as findings
            result = SubagentResult(
                role=role,
                task=task,
                findings=content[:4000],
                structured_data={},
                confidence=0.6,
                citations=[],
            )

        # ── For the code subagent: actually EXECUTE the code ─────
        # This is a real Modal sandbox execution — returns stdout, stderr,
        # files produced. The LLM's predicted output is REPLACED with the
        # real execution result, so the user sees actual data, not hallucinated.
        if role == SubagentRole.CODE and result.structured_data.get("code"):
            try:
                from app.services.code_sandbox import get_code_sandbox

                sandbox = get_code_sandbox()
                exec_result = await sandbox.execute(
                    code=result.structured_data["code"],
                    language=result.structured_data.get("language", "python"),
                    timeout=min(60.0, timeout + 30),
                )

                # Override the LLM's predicted output with real execution results
                if exec_result.error:
                    result.findings = (
                        f"Code execution failed: {exec_result.error}\n"
                        f"Generated code:\n```python\n{result.structured_data.get('code', '')}\n```"
                    )
                    result.confidence = 0.0
                else:
                    output_summary = (exec_result.stdout or "").strip()
                    if len(output_summary) > 2000:
                        output_summary = output_summary[:2000] + "\n... (truncated)"

                    result.findings = (
                        f"Executed in Modal sandbox (exit_code={exec_result.exit_code}, "
                        f"{exec_result.duration_seconds:.2f}s):\n\n"
                        f"```\n{output_summary}\n```"
                    )
                    if exec_result.stderr.strip():
                        result.findings += f"\n\nStderr:\n```\n{exec_result.stderr.strip()[:500]}\n```"
                    if exec_result.files_produced:
                        result.findings += (
                            f"\n\nFiles produced: {', '.join(exec_result.files_produced)}"
                        )
                    # Augment structured_data with real execution results
                    result.structured_data["execution"] = {
                        "exit_code": exec_result.exit_code,
                        "duration_seconds": exec_result.duration_seconds,
                        "sandbox_id": exec_result.sandbox_id,
                        "files_produced": exec_result.files_produced,
                        "timed_out": exec_result.timed_out,
                        "stderr": exec_result.stderr[:1000] if exec_result.stderr else "",
                    }
                    # Higher confidence since the code actually ran
                    result.confidence = min(1.0, result.confidence + 0.1)
            except Exception as exc:
                logger.warning("Code execution failed in subagent: %s", exc)
                result.findings = (
                    f"Code execution sandbox unavailable: {exc}\n"
                    f"Generated code (unexecuted):\n```python\n{result.structured_data.get('code', '')}\n```"
                )
                result.confidence = max(0.0, result.confidence - 0.3)

        logger.info(
            "Subagent %s completed task '%s' (confidence=%.2f)",
            role.value,
            task[:60],
            result.confidence,
        )
        return result
    except Exception as exc:
        import traceback
        # Special-case asyncio.TimeoutError — its str() is empty, which makes
        # the trace useless. Use the timeout value instead.
        if isinstance(exc, asyncio.TimeoutError):
            err_msg = f"LLM call timed out after {timeout}s"
        else:
            err_msg = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "Subagent %s failed: %s\nTraceback:\n%s",
            role.value, err_msg, traceback.format_exc(),
        )
        return SubagentResult(
            role=role,
            task=task,
            findings=f"[{role.value} subagent error: {err_msg}]",
            structured_data={"error": err_msg},
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

    @_lc_tool
    async def async_dispatch_agent(
        task: str,
        code: str,
        context: str = "",
        language: str = "python",
        timeout: float = 120.0,
    ) -> str:
        """Dispatch a long-running code-execution job to Modal in the background.

        This is a NON-BLOCKING dispatch — returns immediately with a job_id.
        Use this when the user wants to run a heavy computation that would
        take more than ~30 seconds (deep learning training, large dataset
        analysis, long simulations).

        The job runs in a Modal sandbox. Progress is reported via WebSocket
        events (JOB_QUEUED, JOB_STARTED, JOB_COMPLETED). The user can
        continue chatting while the job runs.

        Args:
            task: Description of what the code does (for the user's context).
            code: The Python code to execute.
            context: Optional prior findings to include in the report.
            language: 'python', 'r', or 'bash'.
            timeout: Max execution time in seconds.

        Returns:
            JSON with the job_id and a message to relay to the user.
        """
        # Get the session_id from the Supervisor state. We need to access
        # the current state — but the tool function is stateless. We rely
        # on a thread-local or pass session_id via the task string. For
        # simplicity, the supervisor passes session_id encoded in context.
        import json as _json
        import re as _re

        # Extract session_id from context if provided as JSON
        session_id = None
        user_id = None
        m = _re.search(r'"session_id":\s*"([0-9a-f-]+)"', context)
        if m:
            session_id = m.group(1)
        m = _re.search(r'"user_id":\s*"([0-9a-f-]+)"', context)
        if m:
            user_id = m.group(1)
        if not session_id or not user_id:
            return _json.dumps({
                "error": "session_id and user_id must be provided in context",
            })
        import uuid as _uuid
        from app.services.async_jobs import get_job_manager

        mgr = get_job_manager()
        job = await mgr.dispatch(
            session_id=_uuid.UUID(session_id),
            user_id=_uuid.UUID(user_id),
            prompt=task,
            code=code,
            language=language,  # type: ignore[arg-type]
            timeout=timeout,
        )
        return _json.dumps({
            "job_id": job.job_id,
            "status": job.status.value,
            "message": f"Job {job.job_id} dispatched. You can continue chatting — I'll send progress updates and synthesize a final report when it completes.",
        })

    @_lc_tool
    async def async_status_agent(job_id: str, context: str = "") -> str:
        """Check the status of a previously-dispatched async job.

        Use this when the user asks "is my job done?" or "what did the
        job produce?". Returns the current status, progress, and (if
        complete) the full stdout/stderr.

        Args:
            job_id: The job_id returned by async_dispatch_agent.
            context: Optional prior context.
        """
        import json as _json
        import re as _re
        m = _re.search(r'"session_id":\s*"([0-9a-f-]+)"', context)
        if not m:
            return _json.dumps({"error": "session_id required in context"})
        session_id = m.group(1)
        from app.services.async_jobs import get_job_manager

        mgr = get_job_manager()
        job = await mgr.get_job(job_id)
        if job is None or job.session_id != session_id:
            return _json.dumps({"error": f"Job {job_id} not found"})
        result = job.result
        return _json.dumps({
            "job_id": job.job_id,
            "status": job.status.value,
            "progress": job.progress,
            "exit_code": result.exit_code if result else None,
            "stdout": (result.stdout[:3000] if result and result.stdout else ""),
            "stderr": (result.stderr[:1000] if result and result.stderr else ""),
            "files_produced": result.files_produced if result else [],
            "error": result.error if result else None,
            "duration_seconds": (
                (datetime.fromisoformat(result.completed_at.replace("Z", "+00:00"))
                 - datetime.fromisoformat(job.created_at.replace("Z", "+00:00"))
                ).total_seconds()
                if result and result.completed_at else None
            ),
        })

    # The full set of subagent tools the Supervisor can bind
    SUBAGENT_TOOLS = [
        biology_agent,
        math_agent,
        code_agent,
        literature_agent,
        async_dispatch_agent,
        async_status_agent,
    ]

except ImportError:
    # langchain_core not available — provide stubs so import doesn't break
    logger.warning("langchain_core.tools not available — subagent tools disabled")
    SUBAGENT_TOOLS = []
    biology_agent = None  # type: ignore
    math_agent = None  # type: ignore
    code_agent = None  # type: ignore
    literature_agent = None  # type: ignore
    async_dispatch_agent = None  # type: ignore
    async_status_agent = None  # type: ignore


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
    timeout: float = 300.0,
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