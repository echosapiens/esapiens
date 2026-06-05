"""Modal Sandbox integration for executing bioinformatics containers.

Two-sandbox architecture sharing a Modal Volume:
1. Download sandbox (Ubuntu) — fetches input data from the internet.
   Ubuntu has python3, curl, wget for downloads.
2. BioContainer sandbox — mounts the same Volume and runs the tool.

Volume mount path: /data (shared between both sandboxes).
"""

import modal
from app.models import ContainerContract
from app.config import settings

# Shared volume for data transfer between sandboxes
DATA_VOLUME = modal.Volume.from_name("esapiens-data-vol", create_if_missing=True)

# Ubuntu image with python3 for downloading data
DOWNLOAD_IMAGE = (
    modal.Image.from_registry("ubuntu:24.04")
    .apt_install(["python3", "ca-certificates", "curl", "wget"])
)


async def execute_contract_sandbox(contract: ContainerContract) -> dict:
    """
    Execute a ContainerContract using two Modal Sandboxes sharing a Volume.

    1. Ubuntu sandbox downloads input data to /data/input/ on the shared volume.
    2. BioContainer sandbox mounts the same volume and runs the tool command.

    Returns dict with keys: status, stdout, stderr
    """
    if not settings.MODAL_TOKEN_ID or not settings.MODAL_TOKEN_SECRET:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Modal credentials not configured. Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET.",
        }

    try:
        import modal
    except ImportError:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Modal package not installed. Install with: pip install modal",
        }

    image_string = contract.image_string
    if not image_string or not image_string.startswith(
        ("quay.io/", "docker.io/", "ghcr.io/")
    ):
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Unsafe or missing container image: {image_string}",
        }

    try:
        modal_app = await modal.App.lookup.aio(
            "esapiens-bio-compute", create_if_missing=True
        )

        # --- Phase 1: Download data in Ubuntu sandbox ---
        download_cmd = contract.download_command
        if download_cmd:
            download_sb = await modal.Sandbox.create.aio(
                image=DOWNLOAD_IMAGE,
                volumes={"/data": DATA_VOLUME},
                app=modal_app,
                timeout=300,
            )

            dl_proc = await download_sb.exec.aio(
                "bash", "-c", download_cmd,
                timeout=300,
            )
            await dl_proc.wait.aio()
            dl_exit = dl_proc.returncode

            if dl_exit != 0:
                dl_stderr = await dl_proc.stderr.read.aio() or ""
                dl_stdout = await dl_proc.stdout.read.aio() or ""
                await download_sb.terminate.aio()
                return {
                    "status": "error",
                    "stdout": dl_stdout,
                    "stderr": f"Data download failed (exit {dl_exit}): {dl_stderr}",
                }

            await download_sb.terminate.aio()

        # --- Phase 2: Run tool in BioContainer sandbox ---
        bio_image = modal.Image.from_registry(image_string)
        tool_sb = await modal.Sandbox.create.aio(
            image=bio_image,
            volumes={"/data": DATA_VOLUME},
            timeout=contract.container_timeout_seconds,
            app=modal_app,
        )

        tool_cmd = contract.exact_cli_command
        tool_proc = await tool_sb.exec.aio(
            "bash", "-c", tool_cmd,
            timeout=contract.container_timeout_seconds,
        )
        await tool_proc.wait.aio()

        stdout = await tool_proc.stdout.read.aio() or ""
        stderr = await tool_proc.stderr.read.aio() or ""
        exit_code = tool_proc.returncode

        await tool_sb.terminate.aio()

        status = "completed" if exit_code == 0 else "error"

        return {
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
        }

    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Modal sandbox execution failed: {str(e)}",
        }