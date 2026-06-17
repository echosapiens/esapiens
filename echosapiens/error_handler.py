"""
error_handler.py — Error Intervention Routing Engine.

Evaluates sandboxed execution conditions and dynamically handles failures
according to the global ``error_handling_preference``. Supports agentic
self-correction, strict technical (fail-fast) exits, and human-in-the-loop
administrative interrupts via LangGraph's native ``interrupt`` primitive.
"""

from typing import Any, Literal

import structlog
from langgraph.types import interrupt

from .state import EchoSapiensState

logger = structlog.get_logger()


class ErrorInterventionRouter:
    """
    Evaluates sandbox execution outputs and applies error mitigation strategies.

    Supports self-correction, strict technical exits, and administrative
    interrupts. Every method is static so the router can be registered directly
    as a LangGraph node without instantiation.
    """

    @staticmethod
    def route_error_state(
        state: EchoSapiensState,
    ) -> Literal["planning_retry", "fail_fast_exit", "human_review_boundary", "proceed"]:
        """
        Infer direction pathways from runtime state.

        Returns one of ``planning_retry``, ``fail_fast_exit``,
        ``human_review_boundary``, or ``proceed`` based on the presence of
        ``system_errors`` and the configured ``error_handling_preference``.
        """
        if not state.get("system_errors") or state.get("latest_step_in_error") is None:
            return "proceed"

        preference = state.get("error_handling_preference", "agentic_self_correction")
        retry_count = state.get("retry_count", 0)

        logger.warn("error_routing_evaluation", preference=preference, retry_count=retry_count)

        if preference == "agentic_self_correction":
            if retry_count < 3:
                return "planning_retry"
            return "fail_fast_exit"

        elif preference == "human_in_the_loop":
            return "human_review_boundary"

        # Default fallback strategy is immediate exit exposure
        return "fail_fast_exit"

    @staticmethod
    def execute_self_correction(state: EchoSapiensState) -> dict[str, Any]:
        """
        Increments internal failure counter and triggers pipeline recalculations.

        Clears ``system_errors`` so that re-evaluation runs start from a clean
        slate while preserving previously accumulated execution results.
        """
        logger.info("applying_agentic_self_correction", current_retries=state.get("retry_count"))
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            # Clears standard system error properties for re-evaluation runs
            "system_errors": [],
        }

    @staticmethod
    def human_checkpoint_interrupter(state: EchoSapiensState) -> dict[str, Any]:
        """
        Halt the active state machine using LangGraph's native interrupt interface.

        Builds an administrative snapshot of the current failure and pauses
        execution until a manual override is supplied via the API. A ``retry``
        override resumes agentic self-correction; any other action aborts the
        pipeline.
        """
        logger.warn("human_checkpoint_activated", thread_id=state.get("thread_id"))

        # Build state snapshot payload for the administrator
        admin_payload: dict[str, Any] = {
            "error_message": state.get("system_errors", ["Unknown sandbox failure"])[-1],
            "step_id": state.get("latest_step_in_error"),
            "suggestion": (
                "Overwrite biological criteria or parameters to resolve pipeline blockages."
            ),
        }

        # HALT: pause progress until manual action is applied via API.
        user_override: dict[str, Any] = interrupt(admin_payload)

        logger.info("manual_override_received", decision=user_override.get("action"))

        if user_override.get("action") == "retry":
            return {
                "retry_count": state.get("retry_count", 0) + 1,
                "system_errors": [],
                # Temporarily resume self-correction
                "error_handling_preference": "agentic_self_correction",
            }

        # Administrative Abort request
        return {
            "session_status": "failed",
            "system_errors": ["Aborted manually by administrative overrides."],
        }
