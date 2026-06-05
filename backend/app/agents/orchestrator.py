"""Phase 3: Orchestration & Execution Agent."""

from app import modal_exec
from app.models import ContainerContract


class OrchestratorAgent:
    """Dispatches contracts to Modal Sandbox for execution."""

    def __init__(self):
        self.modal_exec = modal_exec

    async def process(self, contract: ContainerContract) -> dict:
        """
        Dispatches the contract to Modal Sandbox for execution.

        1. Validate contract image_string is safe
        2. Execute via Modal Sandbox (async)
        3. Return result dict with stdout, stderr, status
        """
        # Validate image string
        image_string = contract.image_string
        if not image_string or not image_string.startswith(
            ("quay.io/", "docker.io/", "ghcr.io/", "biocontainers/")
        ):
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Invalid or unsafe container image: {image_string}",
            }

        # Execute via Modal sandbox (async)
        result = await self.modal_exec.execute_contract_sandbox(contract)
        return result