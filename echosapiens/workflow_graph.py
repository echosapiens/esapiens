"""
workflow_graph.py — LangGraph Functional Workflow DAG Configuration.

Connects the agent nodes, error-handler nodes, edges, and conditional decision
branches into a complete compiled LangGraph state machine with a
``MemorySaver`` checkpointer for human-in-the-loop recovery.
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents import EchoSapiensAgents
from .error_handler import ErrorInterventionRouter
from .state import EchoSapiensState


def route_post_execution(
    state: EchoSapiensState,
) -> Literal[
    "agentic_correction",
    "human_interruption_checkpoint",
    "fail_fast_terminate",
    "complete_run",
]:
    """
    Conditional-edge decision function following isolated execution.

    Translates the :class:`ErrorInterventionRouter.route_error_state` verdict
    into a concrete node or terminator target understood by the graph.
    """
    decision = ErrorInterventionRouter.route_error_state(state)

    if decision == "planning_retry":
        return "agentic_correction"
    elif decision == "human_review_boundary":
        return "human_interruption_checkpoint"
    elif decision == "fail_fast_exit":
        return "fail_fast_terminate"
    return "complete_run"


def build_workflow_graph(agents: EchoSapiensAgents) -> StateGraph:
    """
    Construct a compiled multi-agent state machine.

    Wires five nodes — ``formulate_hypothesis``, ``plan_workflow``,
    ``execute_isolated_workloads``, ``agentic_correction``, and
    ``human_interruption_checkpoint`` — with sequential forward edges and
    conditional recovery loopbacks, then compiles the graph with a
    ``MemorySaver`` checkpointer.

    Args:
        agents: An :class:`EchoSapiensAgents` instance providing the three
            execution node callables.

    Returns:
        A compiled LangGraph runnable ready to be invoked with a checkpointer
        configuration.
    """
    builder = StateGraph(EchoSapiensState)

    # ── Node Definitions ──
    builder.add_node("formulate_hypothesis", agents.hypothesis_formulation_agent)
    builder.add_node("plan_workflow", agents.workflow_planning_agent)
    builder.add_node("execute_isolated_workloads", agents.isolated_execution_agent)

    builder.add_node("agentic_correction", ErrorInterventionRouter.execute_self_correction)
    builder.add_node(
        "human_interruption_checkpoint", ErrorInterventionRouter.human_checkpoint_interrupter
    )

    # ── Workflow Edges ──
    builder.add_edge(START, "formulate_hypothesis")
    builder.add_edge("formulate_hypothesis", "plan_workflow")
    builder.add_edge("plan_workflow", "execute_isolated_workloads")

    # ── Conditional Error Router Deciders ──
    builder.add_conditional_edges(
        "execute_isolated_workloads",
        route_post_execution,
        {
            "agentic_correction": "agentic_correction",
            "human_interruption_checkpoint": "human_interruption_checkpoint",
            "fail_fast_terminate": END,
            "complete_run": END,
        },
    )

    # Error recovery loopback edges returning focus back onto workflow logic execution nodes
    builder.add_edge("agentic_correction", "plan_workflow")
    builder.add_edge("human_interruption_checkpoint", "plan_workflow")

    # Native MemorySaver checkpointer handles state recovery during HITL overrides
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
