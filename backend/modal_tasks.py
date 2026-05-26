"""
Modal Task Registry — Pre-defined bioinformatics tasks that run on Modal.

Defines Modal container images and remote functions for heavy compute tasks
(STAR alignment, SRA downloads, DESeq2, etc.) plus a registry that
the `run_modal_job` tool in tools.py dispatches to.

The agent can also dynamically create new Modal tasks via `create_modal_tool`.

Authentication: On headless VPS (Hostinger), set MODAL_TOKEN_ID and
MODAL_TOKEN_SECRET in .env — _init_modal_client() reads these at import
time and creates a persistent Modal client. No browser needed.
"""

import os
import json
import time
import traceback
from pathlib import Path
from typing import Any

# Try importing modal — if not installed, tasks will fail gracefully
try:
    import modal

    MODAL_AVAILABLE = True
except ImportError:
    MODAL_AVAILABLE = False


# =============================================================================
# Modal Authentication — support headless/VPS deployment
# =============================================================================


def _init_modal_client():
    """Validate Modal environment and return credential status.

    On a headless VPS (Hostinger), there is no browser for `modal setup`.
    Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET in .env or environment.
    Modern Modal SDK (0.57+) reads these from env vars automatically -
    no explicit client setup required.

    Returns True if Modal SDK is importable, False otherwise.
    """
    if not MODAL_AVAILABLE:
        return False

    token_id = os.environ.get("MODAL_TOKEN_ID", "").strip()
    token_secret = os.environ.get("MODAL_TOKEN_SECRET", "").strip()

    if token_id and token_secret:
        # Modern Modal SDK reads env vars automatically
        pass
    else:
        # No tokens - Modal will fall back to ~/.modal credentials
        pass

    return True


# Check Modal availability on import
# (dotenv is already loaded by main.py before tools.py imports modal_tasks)
MODAL_CREDENTIALS_OK = _init_modal_client()


# =============================================================================
# Pre-defined task schemas (always available, even without Modal SDK)
# =============================================================================

BIO_TASKS: dict[str, dict[str, Any]] = {
    "star_alignment": {
        "app": None,
        "function": None,
        "description": "Run STAR alignment on SRA data (32 cores, 128GB RAM). Returns gene counts and alignment stats.",
        "parameters": {
            "type": "object",
            "properties": {
                "sra_accession": {
                    "type": "string",
                    "description": "SRA run accession (e.g., SRR23642046)",
                },
                "gencode_version": {
                    "type": "string",
                    "description": "GENCODE annotation version (e.g., v44)",
                    "default": "v44",
                },
                "star_index_path": {
                    "type": "string",
                    "description": "Path to pre-built STAR index in /data volume (optional)",
                },
            },
            "required": ["sra_accession"],
        },
    },
    "download_sra": {
        "app": None,
        "function": None,
        "description": "Download FASTQ or SRA files from NCBI. Returns file list and paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "sra_accession": {
                    "type": "string",
                    "description": "SRA run accession (e.g., SRR23642046)",
                },
                "format": {
                    "type": "string",
                    "enum": ["fastq", "sra"],
                    "description": "Download format: 'fastq' (default) or 'sra' (raw archive)",
                    "default": "fastq",
                },
            },
            "required": ["sra_accession"],
        },
    },
    "deseq2": {
        "app": None,
        "function": None,
        "description": "Run DESeq2 differential expression. Requires count matrix + metadata CSV in the /data volume.",
        "parameters": {
            "type": "object",
            "properties": {
                "count_matrix_path": {
                    "type": "string",
                    "description": "Path to CSV count matrix in /data volume",
                },
                "design_formula": {
                    "type": "string",
                    "description": "R design formula (default: ~ condition)",
                    "default": "~ condition",
                },
                "contrast": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Contrast levels [numerator, denominator]",
                },
            },
            "required": ["count_matrix_path"],
        },
    },
}


# =============================================================================
# Modal-dependent definitions — only instantiated when SDK is available
# =============================================================================

if MODAL_AVAILABLE:
    # ---- Container Images ----

    # BioContainers from Quay.io — production-ready, version-locked,
    # maintained by the bioconda community. No more compiling from source.
    #
    # Each image pulls a specific tool pinned by build hash for reproducibility.
    # Python dependencies are pip-installed separately on top.

    # STAR 2.7.11b aligner via BioContainers
    _star_image = modal.Image.from_registry(
        "quay.io/biocontainers/star:2.7.11b--h5ca1c30_8",
        add_python="3.11",
    ).pip_install("pysam")

    # SRA Toolkit 3.4.1 (fasterq-dump, prefetch) via BioContainers
    _sra_image = modal.Image.from_registry(
        "quay.io/biocontainers/sra-tools:3.4.1--h4304569_1",
        add_python="3.11",
    ).pip_install("pysam")

    # DESeq2 1.50.2 (R 4.5 / Bioconductor 3.21) via BioContainers
    # Ships R + BiocManager + DESeq2 pre-installed. No apt installs needed.
    _deseq2_image = modal.Image.from_registry(
        "quay.io/biocontainers/bioconductor-deseq2:1.50.2--r45ha27e39d_0",
        add_python="3.11",
    ).pip_install("pandas", "numpy", "httpx")

    # General GPU image for ML tasks (no biocontainer — PyTorch from pip)
    _gpu_image = modal.Image.debian_slim(python_version="3.11").pip_install(
        "torch", "transformers", "scanpy", "anndata"
    )

    # ---- Modal App Definitions ----

    _star_app = modal.App("esapiens-star-aligner", image=_star_image)
    _sra_app = modal.App("esapiens-sra-download", image=_sra_image)
    _deseq2_app = modal.App("esapiens-deseq2", image=_deseq2_image)
    _gpu_app = modal.App("esapiens-gpu-worker", image=_gpu_image)

    # ---- Shared Volume ----

    _data_volume = modal.Volume.from_name("esapiens-data", create_if_missing=True)

    # ---- Remote Function Definitions ----

    @_star_app.function(
        cpu=16,
        memory=128 * 1024,  # 128 GB RAM
        timeout=7200,  # 2-hour max
        volumes={"/data": _data_volume},
    )
    def run_star_alignment(
        sra_accession: str,
        gencode_version: str = "v44",
        star_index_path: str | None = None,
    ) -> dict[str, Any]:
        """Run STAR alignment on a remote Modal container."""
        import subprocess
        import os

        # Validate SRA accession to prevent shell injection
        sra_accession = _validate_sra_accession(sra_accession)

        work_dir = f"/data/star_jobs/{sra_accession}"
        os.makedirs(work_dir, exist_ok=True)
        output_dir = os.path.join(work_dir, "output")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Step 1: Download FASTQ
            print(f"[STAR] Downloading {sra_accession}...")
            dl_result = subprocess.run(
                [
                    "fasterq-dump",
                    "--split-files",
                    "--threads",
                    "4",
                    sra_accession,
                    "--outdir",
                    work_dir,
                ],
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if dl_result.returncode != 0:
                return {"error": f"fasterq-dump failed: {dl_result.stderr[-2000:]}"}

            fastq_files = [
                f
                for f in os.listdir(work_dir)
                if f.endswith(".fastq") or f.endswith(".fastq.gz")
            ]
            if not fastq_files:
                return {
                    "error": f"No FASTQ files found after download of {sra_accession}"
                }

            # Step 2: Build STAR command
            read_files_param = " ".join(
                [os.path.join(work_dir, f) for f in sorted(fastq_files)]
            )
            if star_index_path:
                index_param = f"--genomeDir {star_index_path}"
            else:
                index_param = f"--genomeDir /data/star_indexes/{gencode_version}"

            star_cmd = (
                f"STAR --runThreadN 16 {index_param} "
                f"--readFilesIn {read_files_param} "
                f"--outFileNamePrefix {output_dir}/ "
                f"--outSAMtype BAM SortedByCoordinate "
                f"--quantMode GeneCounts "
                f"--outSAMattrRGline ID:{sra_accession} SM:{sra_accession} PL:ILLUMINA"
            )

            print(f"[STAR] Running alignment for {sra_accession}...")
            star_result = subprocess.run(
                star_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=7200,
            )

            result = {
                "sra_accession": sra_accession,
                "gencode_version": gencode_version,
                "star_exit_code": star_result.returncode,
                "output_dir": output_dir,
            }

            gene_counts_file = os.path.join(output_dir, "ReadsPerGene.out.tab")
            aligned_bam = os.path.join(output_dir, "Aligned.sortedByCoord.out.bam")

            if os.path.exists(gene_counts_file):
                with open(gene_counts_file) as f:
                    result["gene_counts_preview"] = f.read()[:2000]

            if os.path.exists(aligned_bam):
                result["bam_path"] = aligned_bam

            log_file = os.path.join(output_dir, "Log.final.out")
            if os.path.exists(log_file):
                with open(log_file) as f:
                    result["alignment_log"] = f.read()[:3000]

            return result

        except subprocess.TimeoutExpired:
            return {"error": f"STAR alignment timed out for {sra_accession}"}
        except Exception:
            return {"error": f"STAR alignment failed: {traceback.format_exc()[-3000:]}"}

    @_sra_app.function(
        cpu=4,
        memory=16 * 1024,
        timeout=3600,
        volumes={"/data": _data_volume},
    )
    def download_sra(
        sra_accession: str,
        format: str = "fastq",
    ) -> dict[str, Any]:
        """Download data from NCBI SRA via fasterq-dump or prefetch."""
        import subprocess
        import os

        # Validate SRA accession to prevent shell injection
        sra_accession = _validate_sra_accession(sra_accession)

        out_dir = f"/data/sra_downloads/{sra_accession}"
        os.makedirs(out_dir, exist_ok=True)

        try:
            if format == "fastq":
                result = subprocess.run(
                    [
                        "fasterq-dump",
                        "--split-files",
                        "--threads",
                        "4",
                        sra_accession,
                        "--outdir",
                        out_dir,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
            else:
                result = subprocess.run(
                    ["prefetch", sra_accession, "--max-size", "100G", "-o", out_dir],
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )

            files = os.listdir(out_dir) if os.path.exists(out_dir) else []

            return {
                "sra_accession": sra_accession,
                "format": format,
                "exit_code": result.returncode,
                "output_dir": out_dir,
                "files": files,
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Download timed out for {sra_accession}"}
        except Exception:
            return {"error": f"Download failed: {traceback.format_exc()[-3000:]}"}

    @_deseq2_app.function(
        cpu=4,
        memory=16 * 1024,
        timeout=3600,
        volumes={"/data": _data_volume},
    )
    def run_deseq2(
        count_matrix_path: str,
        design_formula: str = "~ condition",
        contrast: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run DESeq2 differential expression analysis on a count matrix."""
        import subprocess
        import os

        # Sanitize R parameters to prevent code injection
        design_formula = _sanitize_r_param(design_formula)
        if contrast:
            contrast = [_sanitize_r_param(c) for c in contrast]

        work_dir = os.path.dirname(count_matrix_path)
        output_path = os.path.join(work_dir, "deseq2_results.csv")

        r_script = f"""
library(DESeq2)
counts <- read.csv("{count_matrix_path}", row.names=1)
coldata <- read.csv("{count_matrix_path.replace('.csv', '_metadata.csv')}", row.names=1)
dds <- DESeqDataSetFromMatrix(countData=round(counts), colData=coldata, design={design_formula})
dds <- DESeq(dds)
res <- results(dds, contrast=c("{contrast[0] if contrast else 'condition'}", "{contrast[1] if contrast and len(contrast) > 1 else 'reference'}"))
res <- res[order(res$padj),]
write.csv(as.data.frame(res), "{output_path}")
cat("DESeq2 completed\\n")
"""

        r_script_path = os.path.join(work_dir, "deseq2_analysis.R")
        with open(r_script_path, "w") as f:
            f.write(r_script)

        try:
            result = subprocess.run(
                ["Rscript", r_script_path],
                capture_output=True,
                text=True,
                timeout=3600,
            )

            output_exists = os.path.exists(output_path)
            results_preview = ""
            if output_exists:
                with open(output_path) as f:
                    results_preview = f.read()[:5000]

            return {
                "exit_code": result.returncode,
                "output_path": output_path if output_exists else None,
                "results_preview": results_preview,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }

        except subprocess.TimeoutExpired:
            return {"error": "DESeq2 analysis timed out"}
        except Exception:
            return {"error": f"DESeq2 failed: {traceback.format_exc()[-3000:]}"}

    @_gpu_app.function(
        gpu="T4",
        cpu=4,
        memory=16 * 1024,
        timeout=3600,
    )
    def run_gpu_task(
        task_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Generic GPU worker for ML tasks (placeholder)."""
        return {
            "status": "not_implemented",
            "message": f"GPU task type '{task_type}' is not yet pre-defined. Use create_modal_tool to define custom GPU tasks.",
        }

    # Wire up the task registry with live Modal objects
    BIO_TASKS["star_alignment"]["app"] = _star_app
    BIO_TASKS["star_alignment"]["function"] = run_star_alignment
    BIO_TASKS["download_sra"]["app"] = _sra_app
    BIO_TASKS["download_sra"]["function"] = download_sra
    BIO_TASKS["deseq2"]["app"] = _deseq2_app
    BIO_TASKS["deseq2"]["function"] = run_deseq2


# =============================================================================
# Dynamic Modal Tool Creation
# =============================================================================

# Registry for dynamically created modal functions
_dynamic_modal_tasks: dict[str, dict[str, Any]] = {}


def create_modal_task(
    name: str,
    description: str,
    parameters: dict,
    code: str,
    cpu: float = 2.0,
    memory_mb: int = 4096,
    gpu: str | None = None,
    timeout: int = 3600,
    image_packages: list[str] | None = None,
    image_apt_packages: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new Modal function dynamically."""
    if not MODAL_AVAILABLE:
        return {"error": "Modal SDK not installed.", "status": "error"}

    # Sanitize name
    safe_name = name.lower().strip().replace("-", "_").replace(" ", "_")
    if not safe_name.replace("_", "").isalnum():
        return {"error": f"Invalid task name: {name}", "status": "error"}

    # Build the image
    image = modal.Image.debian_slim(python_version="3.11")
    if image_apt_packages:
        image = image.apt_install(*image_apt_packages)
    if image_packages:
        image = image.pip_install(*image_packages)

    # Create a Modal app for this task
    app = modal.App(f"esapiens-dynamic-{safe_name}", image=image)

    # Build the remote function from user code
    func_params = parameters.get("properties", {})
    required_params = parameters.get("required", [])
    param_list = []
    for pname, pdef in func_params.items():
        if pname in required_params:
            param_list.append(pname)
        else:
            default = pdef.get("default")
            param_list.append(
                f"{pname}={repr(default) if default is not None else 'None'}"
            )

    params_sig = ", ".join(param_list)

    # Create the remote function source
    func_code = f"""
def {safe_name}({params_sig}):
    {chr(10).join('    ' + line for line in code.strip().split(chr(10)))}
"""

    func_ns: dict[str, Any] = {}
    try:
        exec(func_code, func_ns)
    except Exception as e:
        return {"error": f"Invalid function code: {e}", "status": "error"}

    raw_func = func_ns[safe_name]

    # Decorate with Modal
    modal_kwargs: dict[str, Any] = {
        "cpu": cpu,
        "memory": memory_mb,
        "timeout": timeout,
    }
    if gpu:
        modal_kwargs["gpu"] = gpu

    remote_func = modal.function(**modal_kwargs)(raw_func)
    app.function()(remote_func)

    # Register
    task_entry = {
        "app": app,
        "function": remote_func,
        "description": description,
        "parameters": parameters,
        "cpu": cpu,
        "memory_mb": memory_mb,
        "gpu": gpu,
        "timeout": timeout,
    }

    _dynamic_modal_tasks[safe_name] = task_entry

    return {
        "status": "created",
        "task": safe_name,
        "description": description,
        "cpu": cpu,
        "memory_mb": memory_mb,
        "gpu": gpu,
        "timeout": timeout,
    }


def _validate_sra_accession(acc: str) -> str:
    """Validate SRA accession format to prevent shell injection."""
    import re as _re

    if not _re.match(r"^[A-Z]{1,3}RR\d+$", acc):
        raise ValueError(
            f"Invalid SRA accession: {acc!r}. Must match pattern like SRR1234567."
        )
    return acc


def _sanitize_r_param(param: str) -> str:
    """Remove shell injection characters from R parameters (design_formula, contrast)."""
    import re as _re

    # Remove semicolons, backticks, and any attempt to close/break R strings
    cleaned = _re.sub(r"[;`]", "", param)
    # Remove obvious R code injection (system calls, file operations)
    cleaned = _re.sub(r"\bsystem\s*\(", "", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"\bfile\s*\(", "", cleaned, flags=_re.IGNORECASE)
    cleaned = _re.sub(r"\bpipe\s*\(", "", cleaned, flags=_re.IGNORECASE)
    return cleaned.strip()


def run_modal_task(
    job_type: str, params: dict[str, Any], workspace: Path | None = None
) -> dict[str, Any]:
    """Execute a registered Modal task with detached job support."""
    if not MODAL_AVAILABLE:
        return {"error": "Modal SDK not installed.", "status": "error"}

    task = BIO_TASKS.get(job_type) or _dynamic_modal_tasks.get(job_type)
    if task is None:
        return {"error": f"Unknown job_type: {job_type}", "status": "error"}

    app = task["app"]
    func = task["function"]

    if app is None or func is None:
        return {
            "error": f"Task '{job_type}' is registered but Modal SDK not available to run it.",
            "status": "error",
        }

    # ── Background Execution Logic ──
    is_background = params.pop("background", False)
    if is_background and workspace:
        job_id = f"modal_{job_type}_{int(time.time())}"
        jobs_dir = workspace / "background_jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_path = jobs_dir / f"{job_id}.json"

        try:
            with app.run():
                call = func.spawn(**params)
                status_data = {
                    "job_id": job_id,
                    "modal_call_id": call.object_id,
                    "job_type": job_type,
                    "status": "running",
                    "start_time": time.time(),
                }
                job_path.write_text(json.dumps(status_data))
                return {
                    "status": "detached",
                    "job_id": job_id,
                    "message": f"Detached Modal job '{job_type}' spawned. Monitor Call ID: {call.object_id}",
                }
        except Exception as e:
            return {"error": f"Failed to spawn Modal task: {e}", "status": "error"}

    # ── Standard Blocking Execution ──
    try:
        with app.run():
            result = func.remote(**params)
            return (
                result
                if isinstance(result, dict)
                else {"status": "success", "result": str(result)}
            )
    except Exception as e:
        return {
            "error": f"Modal task '{job_type}' failed: {e}",
            "traceback": traceback.format_exc()[-3000:],
            "status": "error",
        }


def get_available_tasks() -> list[str]:
    """Return list of all available Modal task names."""
    return list(BIO_TASKS.keys()) + list(_dynamic_modal_tasks.keys())
