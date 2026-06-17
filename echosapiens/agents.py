"""
agents.py — LangGraph Multi-Agent Node Execution Definitions.

Defines the structured Pydantic response schemas and the ``EchoSapiensAgents``
class whose methods serve as LangGraph node functions. The agents operate in
sequence: hypothesis formulation, workflow planning, and isolated sandbox
execution.
"""

from typing import Any

import structlog
from pydantic import BaseModel, Field

from .llm_client import BudgetLLMClient
from .sandbox_manager import SandboxManager
from .state import EchoSapiensState, PlanStep

logger = structlog.get_logger()


# ── Step 1: Scientific Hypothesis Verification Model ──


class HypothesisResponseSchema(BaseModel):
    """Structured LLM response schema for the hypothesis formulation step."""

    formulated_hypothesis: str = Field(
        ...,
        description="The highly specific, testable scientific formulation.",
    )
    required_iterations: int = Field(
        ...,
        description="Number of alignment corrections implemented.",
    )
    approved: bool = Field(
        ...,
        description="Flags if a valid hypothesis is ready for execution mapping.",
    )


# ── Step 2: Scientific Plan Synthesis Model ──


class PlanStepModel(BaseModel):
    """A single granular execution pipeline step as emitted by the planner LLM."""

    step_id: int
    name: str
    tool_image: str
    command_template: str
    expected_output_files: list[str]


class PlanningResponseSchema(BaseModel):
    """Structured LLM response schema for the workflow planning step."""

    execution_plan: list[PlanStepModel]
    planning_summary: str


# ── Agent Node Collection ──


class EchoSapiensAgents:
    """
    Encapsulates sequential agent behavior.

    Each method is a LangGraph node operating on :class:`EchoSapiensState`,
    returning a partial state dictionary that LangGraph merges via the
    declared reducers.
    """

    def __init__(self, llm: BudgetLLMClient, sandbox: SandboxManager) -> None:
        """Initialize the agent collection with shared LLM and sandbox clients.

        Args:
            llm: Budget-aware structured LLM client used for hypothesis and
                planning generation.
            sandbox: Isolated sandbox execution manager used to run each
                planned containerised step.
        """
        self.llm = llm
        self.sandbox = sandbox

    def hypothesis_formulation_agent(self, state: EchoSapiensState) -> dict[str, Any]:
        """
        Step 1 agent node.

        Formulates raw prompt requests into highly testable scientific
        assumptions by invoking the structured LLM with
        :class:`HypothesisResponseSchema`.
        """
        logger.info("hypothesis_agent_execution_started", thread_id=state.get("thread_id"))

        prompt: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "You are a bioinformatics lead modeling strict scientific hypotheses.",
            },
            {
                "role": "user",
                "content": (
                    "Formulate and validate this query into research hypotheses: "
                    f"{state['raw_query']}"
                ),
            },
        ]

        llm_response: HypothesisResponseSchema = self.llm.call_structured(
            prompt, HypothesisResponseSchema
        )

        return {
            "formulated_hypothesis": llm_response.formulated_hypothesis,
            "hypothesis_approved": llm_response.approved,
            "hypothesis_iterations": state.get("hypothesis_iterations", 0) + 1,
            "session_status": "formulation",
        }

    def workflow_planning_agent(self, state: EchoSapiensState) -> dict[str, Any]:
        """
        Step 2 agent node.

        Synthesizes execution paths mapped directly to Docker containers on
        quay.io by invoking the structured LLM with
        :class:`PlanningResponseSchema`, then maps the returned
        :class:`PlanStepModel` list into :class:`PlanStep` TypedDicts.
        """
        logger.info("planning_agent_execution_initiated", thread_id=state.get("thread_id"))

        prompt: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "Produce a robust plan mapped directly to quay.io Docker containers.",
            },
            {
                "role": "user",
                "content": (
                    f"Hypothesis validated: {state['formulated_hypothesis']}. "
                    "Plan execution accordingly."
                ),
            },
        ]

        llm_response: PlanningResponseSchema = self.llm.call_structured(
            prompt, PlanningResponseSchema
        )

        # Map step attributes to list of step dictionaries
        steps: list[PlanStep] = [
            PlanStep(
                step_id=s.step_id,
                name=s.name,
                tool_image=s.tool_image,
                command_template=s.command_template,
                expected_output_files=s.expected_output_files,
            )
            for s in llm_response.execution_plan
        ]

        return {
            "execution_plan": steps,
            "planning_summary": llm_response.planning_summary,
            "session_status": "planning",
        }

    def isolated_execution_agent(self, state: EchoSapiensState) -> dict[str, Any]:
        """
        Step 3 agent node.

        Orchestrates direct modal container configurations sequentially. For
        each step in the ``execution_plan`` it delegates to the sandbox
        manager, building an :class:`ExecutionResult` log and an
        ``intermediate_artifacts`` mapping. On the first failing step it
        returns early, populating ``system_errors`` so the error router can
        decide on a recovery path.
        """
        logger.info("isolated_execution_agent_started", thread_id=state.get("thread_id"))

        plans: list[PlanStep] = state.get("execution_plan") or []
        execution_log: list[dict[str, Any]] = []
        artifacts: dict[str, Any] = {}

        for step in plans:
            # Map parameters utilizing metadata structures
            result: dict[str, Any] = self.sandbox.execute_isolated_step(
                step_id=step["step_id"],
                tool_image=step["tool_image"],
                command_template=step["command_template"],
                input_files=list(state.get("input_artifacts", [])),
                expected_outputs=step["expected_output_files"],
            )

            execution_log.append(
                {
                    "step_id": step["step_id"],
                    "exit_code": result["exit_code"],
                    "stdout_summary": result["stdout_summary"],
                    "stderr_summary": result["stderr_summary"],
                    "uploaded_outputs": result["output_file_manifest"],
                    "success": result["success"],
                }
            )

            # Map tracking references to outputs if successful
            if result["success"]:
                for out_meta in result["output_file_manifest"]:
                    artifacts[out_meta["file_name"]] = out_meta
            else:
                # Intercept non-zero execution exit streams immediately
                return {
                    "execution_results": execution_log,
                    "intermediate_artifacts": artifacts,
                    "latest_step_in_error": step["step_id"],
                    "session_status": "running",
                    "system_errors": [
                        f"Step {step['step_id']} failed with code {result['exit_code']}"
                    ],
                }

        return {
            "execution_results": execution_log,
            "intermediate_artifacts": artifacts,
            "latest_step_in_error": None,
            "session_status": "completed",
        }
