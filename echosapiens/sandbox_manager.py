"""
sandbox_manager.py - Ephemeral Micro-Compute Sandbox Orchestration Layer

Launches secure, ephemeral sandboxes running bioinformatics workflows on Modal.
Signs data locations beforehand, passes access parameters into the sandbox, and
force-streams sandbox output back to GCS without routing file buffers through
the host runtime memory.
"""

import uuid
from typing import Any

import modal
import structlog

from .config import Settings
from .gcs_manager import GCSManager
from .state import GCSFileMetadata

logger = structlog.get_logger()

# Shared Global App reference specifically designated for sandboxing operations
sandbox_app = modal.App.lookup("echosapiens-sandboxes", create_if_missing=True)


class SandboxManager:
    """Maintains complete isolation over sandbox lifecycles.

    Streams input sequences inside the virtual environments via pre-signed GETs,
    and handles uploads back to GCS via pre-signed PUT signature requests.
    """

    def __init__(self, settings: Settings, gcs_manager: GCSManager) -> None:
        """Initialize the sandbox manager with settings and a GCS URL signer.

        Args:
            settings: System settings containing sandbox CPU/memory/timeout
                limits and bucket configuration.
            gcs_manager: GCSManager instance used to mint pre-signed URLs.
        """
        self.settings = settings
        self.gcs = gcs_manager

    def execute_isolated_step(
        self,
        step_id: int,
        tool_image: str,
        command_template: str,
        input_files: list[GCSFileMetadata],
        expected_outputs: list[str],
    ) -> dict[str, Any]:
        """Spawn a highly-confined sandbox on Modal to run a bioinformatics tool safely.

        Downloads input artifacts via pre-signed GET URLs, executes the
        rendered command, then uploads expected outputs via pre-signed PUT
        URLs — all inside the sandbox, never through orchestrator memory.

        Args:
            step_id: Numeric identifier of the pipeline step being executed.
            tool_image: OCI registry reference for the bioinformatics tool
                (e.g. ``quay.io/biocontainers/samtools:1.20``).
            command_template: CLI command with ``{{INPUT_N}}`` and
                ``{{OUTPUT_name}}`` placeholders to be resolved against the
                sandbox filesystem.
            input_files: Metadata for each input artifact, including a
                pre-signed download URL.
            expected_outputs: Filenames the tool is expected to produce in
                the sandbox output directory.

        Returns:
            A dict with ``exit_code``, ``stdout_summary``, ``stderr_summary``,
            ``output_file_manifest`` (list of :class:`GCSFileMetadata`), and
            ``success``.
        """
        logger.info("spawning_sandbox", step_id=step_id, tool_image=tool_image)
        session_token = uuid.uuid4().hex[:12]

        # 1. Prepare sandboxed paths inside target volumes
        work_dir = f"/work_{session_token}"
        input_dir = f"{work_dir}/inputs"
        output_dir = f"{work_dir}/outputs"

        # Prepare environment variables dynamically
        environment_vars: dict[str, str] = {}
        download_command = "mkdir -p " + input_dir + " " + output_dir + " && "

        # Map input files internally inside sandbox environments via signed downloads
        for idx, file_meta in enumerate(input_files):
            sandbox_input_path = f"{input_dir}/{file_meta['file_name']}"
            download_command += (
                f"curl -sL '{file_meta['signed_download_url']}'"
                f" -o {sandbox_input_path} && "
            )
            environment_vars[f"INPUT_FILE_{idx}"] = sandbox_input_path

        # Resolve command arguments based on internal storage mappings
        resolved_command = command_template
        for idx, file_meta in enumerate(input_files):
            resolved_command = resolved_command.replace(
                f"{{{{INPUT_{idx}}}}}", f"{input_dir}/{file_meta['file_name']}"
            )

        # Replace expected outputs dynamically matching workspace definitions
        for output_file in expected_outputs:
            resolved_command = resolved_command.replace(
                f"{{{{OUTPUT_{output_file}}}}}", f"{output_dir}/{output_file}"
            )

        # Combine download, execution, and upload sequences
        combined_exec_expr = download_command + f"cd {work_dir} && {resolved_command}"

        # Formulate pre-signed PUT handlers to enable output streaming directly out of the sandbox
        upload_map: dict[str, str] = {}
        for output_file in expected_outputs:
            gcs_dest_blob = f"runs/{session_token}/step_{step_id}/{output_file}"
            signed_put_url = self.gcs.generate_upload_signed_url(gcs_dest_blob)
            upload_map[output_file] = signed_put_url

            # Chain binary push operations
            combined_exec_expr += (
                f" && curl -X PUT -H 'Content-Type: application/octet-stream' "
                f"--upload-file {output_dir}/{output_file} '{signed_put_url}'"
            )

        # Safe isolation: enforce strict runtime limitations per task
        img = modal.Image.from_registry(tool_image, add_python="3.11").apt_install("curl", "bash")

        sb = modal.Sandbox.create(
            "bash",
            "-c",
            combined_exec_expr,
            image=img,
            app=sandbox_app,
            cpu=self.settings.sandbox_default_cpu,
            memory=self.settings.sandbox_default_memory_mb,
            timeout=self.settings.sandbox_timeout_seconds,
            env=environment_vars,
        )

        # Block gracefully until processing is complete
        sb.wait()

        exit_code = sb.returncode
        stdout = sb.stdout.read()
        stderr = sb.stderr.read()

        logger.info("sandbox_execution_concluded", step_id=step_id, exit_code=exit_code)

        # Build output metadata structures to return to the graph
        output_file_manifest: list[GCSFileMetadata] = []
        if exit_code == 0:
            for output_file in expected_outputs:
                gcs_dest_blob = f"runs/{session_token}/step_{step_id}/{output_file}"
                download_signed = self.gcs.generate_download_signed_url(gcs_dest_blob)

                # Attempt to fetch real metadata (size + content_type) from GCS
                # now that the object has been uploaded; fall back to sensible
                # placeholders if the blob is not yet readable (eventual consistency).
                blob_meta = self.gcs.get_blob_metadata(gcs_dest_blob)

                output_file_manifest.append(
                    {
                        "file_name": output_file,
                        "gcs_uri": f"gs://{self.settings.gcs_bucket_name}/{gcs_dest_blob}",
                        "signed_download_url": download_signed,
                        "size_bytes": blob_meta["size_bytes"]
                        if blob_meta
                        else 0,  # Retrieved dynamically by backend downstream pipelines later
                        "content_type": blob_meta["content_type"]
                        if blob_meta
                        else "application/octet-stream",
                    }
                )

        return {
            "exit_code": exit_code,
            "stdout_summary": stdout[-2000:],  # Tail logs
            "stderr_summary": stderr[-2000:],
            "output_file_manifest": output_file_manifest,
            "success": exit_code == 0,
        }
