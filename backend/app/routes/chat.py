"""Chat route — SSE streaming endpoint for real-time pipeline execution and casual chat."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.models import PipelineRequest
from app.openrouter import OpenRouterClient
from app.agents.research import ResearchAgent
from app.agents.contract import ContractAgent
from app.agents.orchestrator import OrchestratorAgent
from app.intent import classify_intent
from app import database

router = APIRouter()

_openrouter_client = None
_research_agent = None
_contract_agent = None
_orchestrator_agent = None


def _get_agents():
    global _openrouter_client, _research_agent, _contract_agent, _orchestrator_agent
    if _research_agent is None:
        _openrouter_client = OpenRouterClient()
        _research_agent = ResearchAgent(_openrouter_client)
        _contract_agent = ContractAgent()
        _orchestrator_agent = OrchestratorAgent()
    return _openrouter_client, _research_agent, _contract_agent, _orchestrator_agent


async def _casual_chat(openrouter_client: OpenRouterClient, prompt: str):
    """Casual chat mode — streams LLM response as tokens."""
    yield {"event": "phase", "data": json.dumps({"type": "chat", "phase": "chat", "status": "start"})}

    system_prompt = (
        "You are Silas, an expert bioinformatician and the sentient core of the E.sapiens platform. "
        "You are helpful, knowledgeable, and speak with precision. "
        "Respond conversationally but with technical depth when appropriate. "
        "Keep responses concise unless asked to elaborate. "
        "If the user greets you, greet back. If they ask about your capabilities, describe them."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    if openrouter_client and openrouter_client.api_key:
        result = openrouter_client.chat_completion(messages, temperature=0.7)
        if "error" not in result:
            response = result.get("content", "I'm here. What bioinformatics work should we tackle?")
        else:
            response = "Good to connect. What bioinformatics analysis are you working on?"
    else:
        response = "I'm Silas, the E.sapiens orchestrator. I can help with bioinformatics pipelines. Try asking me to align sequences, quantify expression, or check alignment statistics."

    words = response.split(" ")
    for i, word in enumerate(words):
        token = word + (" " if i < len(words) - 1 else "")
        yield {"event": "token", "data": json.dumps({"token": token})}
        await asyncio.sleep(0.02)

    yield {"event": "phase", "data": json.dumps({"type": "chat", "phase": "chat", "status": "end"})}
    yield {"event": "complete", "data": json.dumps({"type": "chat"})}


async def _run_pipeline(
    prompt: str,
    research_agent: ResearchAgent,
    contract_agent: ContractAgent,
    orchestrator_agent: OrchestratorAgent,
):
    """Bioinformatics pipeline mode — 3-phase execution with streaming."""
    job_id = str(uuid.uuid4())
    database.create_job(job_id, prompt)

    try:
        # Phase 1: Research
        yield {"event": "phase", "data": json.dumps({"phase": "research", "status": "start"})}
        yield {"event": "thought", "data": json.dumps({"phase": "research", "message": "Analyzing your request to identify the required bioinformatics tool..."})}

        research_output = research_agent.process(prompt)

        tool_name = research_output.get("tool_name", "unknown")
        tool_desc = research_output.get("tool_description", "")
        image = research_output.get("suggested_image", "")

        yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Identified tool: {tool_name} — {tool_desc}"})}
        if image:
            yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Resolved container image: {image}"})}

        # Stream search findings
        findings = research_output.get("search_findings", {})
        if findings and findings.get("search_summary"):
            yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Searched web docs: {findings.get('search_summary', '')[:150]}"})}
        if findings and findings.get("sources"):
            sources_str = ", ".join(findings["sources"][:3])
            yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Sources: {sources_str}"})}

        # Stream generated command
        gen_cmd = research_output.get("generated_command", "")
        if gen_cmd:
            yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Generated command: {gen_cmd[:200]}"})}

        inputs = research_output.get("required_inputs", [])
        if inputs:
            yield {"event": "thought", "data": json.dumps({"phase": "research", "message": f"Expected inputs: {', '.join(i.get('file_type', '') for i in inputs)}"})}

        yield {"event": "result", "data": json.dumps({"phase": "research", "research": research_output})}
        yield {"event": "phase", "data": json.dumps({"phase": "research", "status": "end"})}

        # Phase 2: Contract
        yield {"event": "phase", "data": json.dumps({"phase": "contract", "status": "start"})}
        yield {"event": "thought", "data": json.dumps({"phase": "contract", "message": "Generating container contract with verified image and sanitized command..."})}

        contract = contract_agent.process(research_output)

        yield {"event": "thought", "data": json.dumps({"phase": "contract", "message": f"Container: {contract.image_string}"})}
        yield {"event": "thought", "data": json.dumps({"phase": "contract", "message": f"Download: {contract.download_command[:200] if contract.download_command else 'none needed'}"})}
        yield {"event": "thought", "data": json.dumps({"phase": "contract", "message": f"Tool command: {contract.exact_cli_command[:200]}"})}

        yield {"event": "result", "data": json.dumps({"phase": "contract", "contract": contract.model_dump()})}
        yield {"event": "phase", "data": json.dumps({"phase": "contract", "status": "end"})}

        # Phase 3: Execute
        yield {"event": "phase", "data": json.dumps({"phase": "execute", "status": "start"})}
        if contract.download_command:
            yield {"event": "thought", "data": json.dumps({"phase": "execute", "message": "Phase 3a: Downloading input data in Ubuntu sandbox..."})}
        yield {"event": "thought", "data": json.dumps({"phase": "execute", "message": f"Phase 3b: Running {tool_name} in BioContainer..."})}

        execution_result = await orchestrator_agent.process(contract)

        stdout = execution_result.get("stdout", "")
        stderr = execution_result.get("stderr", "")

        if stdout:
            for line in stdout.split("\n"):
                if line.strip():
                    yield {"event": "log", "data": json.dumps({"phase": "execute", "message": line.strip()})}

        if stderr:
            for line in stderr.split("\n"):
                if line.strip():
                    # Bioinformatics tools write progress to stderr by convention
                    # Only flag as error if the job failed
                    yield {"event": "log", "data": json.dumps({"phase": "execute", "message": line.strip(), "level": "stderr"})}

        status = execution_result.get("status", "error")
        has_real_error = status != "success" and stderr
        if status == "success":
            yield {"event": "thought", "data": json.dumps({"phase": "execute", "message": "Pipeline completed successfully."})}
        else:
            error_msg = execution_result.get("stderr", "Unknown error")
            yield {"event": "error", "data": json.dumps({"message": error_msg})}

        yield {"event": "result", "data": json.dumps({"phase": "execute", "execution": execution_result})}
        yield {"event": "phase", "data": json.dumps({"phase": "execute", "status": "end"})}

        # Normalize status: Modal returns "success", frontend expects "completed"
        db_status = "completed" if status == "success" else status
        # Only store stderr as "error" in DB when the job actually failed
        db_error = stderr if has_real_error else None
        database.update_job(
            job_id,
            status=db_status,
            contract_json=contract.model_dump_json() if contract else None,
            stdout=stdout,
            stderr=stderr,
            error=db_error,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        yield {"event": "complete", "data": json.dumps({"job_id": job_id, "status": status})}

    except Exception as e:
        database.update_job(job_id, status="failed", error=str(e), completed_at=datetime.now(timezone.utc).isoformat())
        yield {"event": "error", "data": json.dumps({"message": str(e)})}
        yield {"event": "complete", "data": json.dumps({"job_id": job_id, "status": "failed"})}


@router.post("/chat/stream")
async def chat_stream(request: Request, body: PipelineRequest):
    """SSE streaming endpoint. Routes casual chat to LLM, bio tasks to pipeline."""

    async def event_generator():
        openrouter_client, research_agent, contract_agent, orchestrator_agent = _get_agents()

        intent = classify_intent(body.user_prompt)

        if intent == "chat":
            async for event in _casual_chat(openrouter_client, body.user_prompt):
                yield event
        else:
            async for event in _run_pipeline(body.user_prompt, research_agent, contract_agent, orchestrator_agent):
                yield event

    return EventSourceResponse(event_generator())