"""Pipeline route — POST /api/v1/run-pipeline."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from app.models import PipelineRequest, PipelineResponse, JobStatus
from app.graph import PipelineGraph
from app.openrouter import OpenRouterClient
from app.agents.research import ResearchAgent
from app.agents.contract import ContractAgent
from app.agents.orchestrator import OrchestratorAgent
from app import database
from app.limiter import limiter
from app.security import get_current_user

router = APIRouter()

# Build agent graph lazily
_openrouter_client = None
_pipeline_graph = None


def _get_graph() -> PipelineGraph:
    global _openrouter_client, _pipeline_graph
    if _pipeline_graph is None:
        _openrouter_client = OpenRouterClient()
        research_agent = ResearchAgent(_openrouter_client)
        contract_agent = ContractAgent()
        orchestrator_agent = OrchestratorAgent()
        _pipeline_graph = PipelineGraph(
            research_agent=research_agent,
            contract_agent=contract_agent,
            orchestrator_agent=orchestrator_agent,
        )
    return _pipeline_graph


@router.post("/run-pipeline", response_model=PipelineResponse)
@limiter.limit("10/minute")
async def run_pipeline(request: Request, body: PipelineRequest, user: dict = Depends(get_current_user)):
    """
    Execute the 3-phase pipeline synchronously.
    1. Research & Discovery → 2. Contract Spec → 3. Orchestration
    Returns job results including contract, cost estimate, and execution output.
    """
    # Generate job ID
    job_id = str(uuid.uuid4())

    # Save to DB
    database.create_job(job_id, body.user_prompt)

    try:
        # Run the graph
        graph = _get_graph()
        result = graph.run(
            user_prompt=body.user_prompt,
            data_bucket_url=body.data_bucket_url,
        )

        # Extract results
        status = result.get("status", "failed")
        contract = result.get("contract")
        execution_result = result.get("execution_result")
        error = result.get("error")

        # Update DB with results
        update_fields = {
            "status": status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        if contract:
            update_fields["contract_json"] = contract.model_dump_json()

        if execution_result:
            update_fields["stdout"] = execution_result.get("stdout")
            update_fields["stderr"] = execution_result.get("stderr")

        if error:
            update_fields["error"] = error

        database.update_job(job_id, **update_fields)

        return PipelineResponse(
            job_id=job_id,
            status=JobStatus(status),
            contract=contract,
            cost_estimate=None,
        )

    except Exception as e:
        # Mark as failed in DB
        database.update_job(
            job_id,
            status="failed",
            error=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        return PipelineResponse(
            job_id=job_id,
            status=JobStatus.FAILED,
            contract=None,
            cost_estimate=None,
        )