"""LangGraph 3-phase state graph for the bioinformatics pipeline.

Uses async execution for the orchestrate node to avoid blocking the event loop.
"""

import asyncio
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from app.models import ContainerContract, CostEstimate
from app.agents.research import ResearchAgent
from app.agents.contract import ContractAgent
from app.agents.orchestrator import OrchestratorAgent


class AgentState(TypedDict):
    user_prompt: str
    data_bucket_url: str
    research_output: Optional[dict]
    contract: Optional[ContainerContract]
    cost_estimate: Optional[CostEstimate]
    job_id: Optional[str]
    execution_result: Optional[dict]
    error: Optional[str]
    status: str


class PipelineGraph:
    """Linear 3-phase state graph: Research -> Contract -> Orchestrate."""

    def __init__(
        self,
        research_agent: ResearchAgent,
        contract_agent: ContractAgent,
        orchestrator_agent: OrchestratorAgent,
    ):
        self.research = research_agent
        self.contract = contract_agent
        self.orchestrator = orchestrator_agent

        # Build linear state graph
        workflow = StateGraph(AgentState)
        workflow.add_node("research", self._research_node)
        workflow.add_node("contract", self._contract_node)
        workflow.add_node("orchestrate", self._orchestrate_node)
        workflow.set_entry_point("research")
        workflow.add_edge("research", "contract")
        workflow.add_edge("contract", "orchestrate")
        workflow.add_edge("orchestrate", END)
        self.app = workflow.compile()

    def _research_node(self, state: AgentState) -> AgentState:
        """Phase 1: Research & Discovery."""
        state["research_output"] = self.research.process(state["user_prompt"])
        state["status"] = "researching"
        return state

    def _contract_node(self, state: AgentState) -> AgentState:
        """Phase 2: Contract & Pipeline Spec."""
        contract = self.contract.process(state["research_output"])
        state["contract"] = contract
        state["status"] = "contracting"
        return state

    def _orchestrate_node(self, state: AgentState) -> AgentState:
        """Phase 3: Orchestration & Execution (runs async in event loop)."""
        # Run the async orchestrate in the current event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — create a new task
                result = asyncio.run_coroutine_threadsafe(
                    self.orchestrator.process(state["contract"]), loop
                ).result()
            else:
                result = loop.run_until_complete(
                    self.orchestrator.process(state["contract"])
                )
        except RuntimeError:
            # No event loop running — create one
            result = asyncio.run(self.orchestrator.process(state["contract"]))

        state["execution_result"] = result
        state["status"] = (
            "completed" if result.get("status") == "success" else "failed"
        )
        if result.get("status") != "success":
            state["error"] = result.get("stderr", "Unknown execution error")
        return state

    def run(self, user_prompt: str, data_bucket_url: str = "/data/input/") -> dict:
        """
        Execute the full pipeline synchronously.
        Returns the final AgentState as a dict.
        """
        initial_state: AgentState = {
            "user_prompt": user_prompt,
            "data_bucket_url": data_bucket_url,
            "research_output": None,
            "contract": None,
            "cost_estimate": None,
            "job_id": None,
            "execution_result": None,
            "error": None,
            "status": "pending",
        }

        result = self.app.invoke(initial_state, config=RunnableConfig(recursion_limit=50))
        return result