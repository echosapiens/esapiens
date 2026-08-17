"""Phase 2: Contract & Pipeline Spec Agent.

Generates two separate commands:
1. download_command — runs in an Ubuntu sandbox (has python3, curl, wget)
   to fetch real input data from the internet.
2. tool_command — runs inside the BioContainer to execute the tool.

This separation is necessary because most BioContainers lack python3/curl/wget
and cannot download files. The download happens in a full Ubuntu VM first,
then the BioContainer mounts the same volume with the data already present.
"""

from app.models import ContainerContract, FileRequirement
from app.security import sanitize_cli_command


def _extract_download_steps(command: str) -> tuple[str, str]:
    """Split a compound command into download steps and tool steps.

    Download steps are python3/printf commands that fetch or create input data.
    Tool steps are the actual bioinformatics commands.

    Returns (download_command, tool_command).
    """
    parts = command.split(" && ")
    download_parts = []
    tool_parts = []

    for part in parts:
        stripped = part.strip()
        if not stripped or stripped == "mkdir -p /data/output":
            # mkdir goes into the tool command (BioContainer creates its own dirs)
            continue
        # Identify download/data-prep steps
        if any(stripped.startswith(prefix) for prefix in [
            "python3 -c",      # python3 download
            "printf",          # inline FASTA data
            "curl",            # curl download
            "wget",            # wget download
        ]):
            download_parts.append(stripped)
        else:
            tool_parts.append(stripped)

    download_cmd = " && ".join(download_parts) if download_parts else ""
    tool_cmd = " && ".join(tool_parts) if tool_parts else command

    return download_cmd, tool_cmd


def _build_command(research_output: dict) -> str:
    """Build the tool-only command (no downloads).

    Downloads are handled separately in modal_exec.py.
    """
    generated = research_output.get("generated_command", "")

    if not generated:
        return "echo 'No command generated'"

    generated = sanitize_cli_command(generated)
    _, tool_cmd = _extract_download_steps(generated)

    if not tool_cmd:
        return "echo 'No tool command found'"

    # Ensure output dir exists
    return f"mkdir -p /data/output && {tool_cmd}"


def _build_download_command(research_output: dict) -> str:
    """Build the download command from resolved data sources.

    Uses deterministic download commands from data_resolver instead of
    extracting from the LLM-generated command (which may hallucinate URLs).
    Returns empty string if no downloads needed.
    """
    download_commands = research_output.get("download_commands", [])
    if not download_commands:
        return ""

    # Join all download commands with &&
    download_str = " && ".join(download_commands)
    return f"mkdir -p /data/input && {download_str}"


class ContractAgent:
    """Validates and wraps research output into a ContainerContract."""

    def process(self, research_output: dict) -> ContainerContract:
        try:
            inputs_raw = research_output.get("required_inputs", [])
            outputs_raw = research_output.get("expected_outputs", [])
            inputs = [
                FileRequirement(
                    file_type=inp.get("file_type", "fasta"),
                    mount_path=inp.get("mount_path", "/data/input/"),
                    description=inp.get("description", ""),
                )
                for inp in inputs_raw
            ] or [FileRequirement(file_type="fasta", mount_path="/data/input/", description="Input file")]
            outputs = [
                FileRequirement(
                    file_type=out.get("file_type", "txt"),
                    mount_path=out.get("mount_path", "/data/output/"),
                    description=out.get("description", ""),
                )
                for out in outputs_raw
            ] or [FileRequirement(file_type="txt", mount_path="/data/output/", description="Output file")]

            # Extract download and tool commands separately
            download_cmd = _build_download_command(research_output)
            tool_cmd = _build_command(research_output)

            return ContainerContract(
                image_string=research_output.get("suggested_image", ""),
                exact_cli_command=tool_cmd,
                download_command=download_cmd,
                inputs=inputs,
                outputs=outputs,
                container_timeout_seconds=1200,
            )
        except Exception as e:
            return ContainerContract(
                image_string="",
                exact_cli_command=f"echo 'Contract error: {e}'",
                download_command="",
                inputs=[],
                outputs=[],
                container_timeout_seconds=60,
            )