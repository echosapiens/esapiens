"""
Bioinformatics Tools — E.sapiens agent tool layer.

Provides JSON-schema tool definitions and corresponding Python functions
for LangGraph tool-callable nodes.

Tool result protocol
  Every tool returns a ToolResult (from result.py). Never a raw dict.
  execute_tool() serializes ToolResult.to_dict() to JSON for the LLM.

Decorator pattern
  Use @register_tool("name") on every function. This:
    1. Adds the function to TOOL_IMPLS for dispatch
    2. Adds the definition to TOOL_DEFINITIONS (built at module load time)
    3. Wraps the function with @timed for automatic elapsed_ms tracking

Tool categories
  Local (VPS):      download_pdb, parse_structure, search_literature,
                    download_tcga_survival, run_python_plot, plotly_plot,
                    execute_python, create_tool, run_bio_pipeline
  Modal (cloud):    run_modal_job, create_modal_tool
  Meta:             get_job_status, list_available_tools
"""

from __future__ import annotations

from typing import Any, Optional
import os, json, httpx, subprocess, sys, tempfile
import base64, textwrap, io, types, threading, time
from pathlib import Path

from result import ToolResult, ToolStatus, timed  # noqa: F401

# ── Shared HTTP headers for NCBI/GDC API compliance ───────────────────────────

HEADERS = {"User-Agent": "E.sapiens/1.0 (contact: research@example.edu)"}

# ════════════════════════════════════════════════════════════════════════════════
# Secret Hygiene — prevent agent code-exec tools from leaking API keys
# ════════════════════════════════════════════════════════════════════════════════

_SECRET_ENV_VARS = {
    "OPENROUTER_API_KEY", "BRAVE_SEARCH_API_KEY",
    "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "JWT_SECRET",
}


def _make_safe_os():
    _os = sys.modules["os"]
    _safe_environ = types.MappingProxyType({
        k: ("***REDACTED***" if k in _SECRET_ENV_VARS else v)
        for k, v in _os.environ.items()
    })
    safe = types.ModuleType("os_safe")
    for attr in dir(_os):
        if attr == "environ":
            continue
        try:
            setattr(safe, attr, getattr(_os, attr))
        except (AttributeError, TypeError):
            pass
    safe.environ = _safe_environ
    safe.getenv = lambda key, default=None: _safe_environ.get(key, default)
    return safe


_safe_os = _make_safe_os()

# ════════════════════════════════════════════════════════════════════════════════
# Restricted builtins — only allow safe names in exec() sandboxes
# ════════════════════════════════════════════════════════════════════════════════

_SAFE_BUILTINS = {
    "print": print, "len": len, "range": range, "int": int, "float": float,
    "str": str, "list": list, "dict": dict, "tuple": tuple, "set": set,
    "bool": bool, "type": type, "isinstance": isinstance, "enumerate": enumerate,
    "sorted": sorted, "reversed": reversed, "zip": zip, "map": map, "filter": filter,
    "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
    "hasattr": hasattr, "getattr": getattr,
    "True": True, "False": False, "None": None,
}

# Whitelist-safe __import__ — only allows known scientific packages.
# This restores import capability within exec() without compromising the sandbox.
# The user can still only access packages we explicitly allow here.
_ALLOWED_IMPORTS = frozenset({
    "numpy", "np",
    "pandas", "pd",
    "matplotlib", "mpl",
    "seaborn", "sns",
    "sklearn", "scipy", "statsmodels",
    "bioframe", "pyBigWig",
    "plotly", "plotly_express",
    "json", "math", "re", "datetime", "collections", "itertools",
    "pathlib", "typing",
})

# Capture the real Python __import__ at module load time (before _SAFE_BUILTINS is built)
_real_import = __builtins__["__import__"]


def _safe_import(name: str, *args, **kwargs):
    root = name.split(".")[0]
    if root not in _ALLOWED_IMPORTS:
        raise ImportError(f"Sandbox restriction: '{root}' is not allowed. Allowed: {sorted(_ALLOWED_IMPORTS)}")
    return _real_import(name, *args, **kwargs)


# Add to _SAFE_BUILTINS so exec() sandboxes can do `import numpy` freely
_SAFE_BUILTINS["__import__"] = _safe_import

# ════════════════════════════════════════════════════════════════════════════════
# Tool Registry — decorator-based (not a manual dict)
# ════════════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict] = []
TOOL_IMPLS: dict[str, callable] = {}


def register_tool(name: str):
    """Decorator: register a function as a named tool.

    Usage:
        @register_tool("my_tool")
        def my_tool(...) -> ToolResult:
            ...
    """
    def decorator(fn: callable) -> callable:
        # Build JSON-schema definition from function signature
        import inspect
        try:
            hints = fn.__annotations__
            sig = inspect.signature(fn)
            params = {}
            required = []
            for pname, p in sig.parameters.items():
                if pname in ("self", "kwargs"):
                    continue
                ptype = hints.get(pname, "string")
                param_def: dict[str, Any] = {"type": "string"}
                if p.default is not inspect.Parameter.empty:
                    param_def["default"] = p.default
                else:
                    required.append(pname)
                params[pname] = param_def
            definition = {
                "name": name,
                "description": fn.__doc__ or "No description.",
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": required,
                },
            }
        except Exception:
            definition = {
                "name": name,
                "description": fn.__doc__ or "No description.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            }
        TOOL_DEFINITIONS.append(definition)
        TOOL_IMPLS[name] = fn
        return fn
    return decorator


# ════════════════════════════════════════════════════════════════════════════════
# Local Tools (VPS)
# ════════════════════════════════════════════════════════════════════════════════

@register_tool("download_pdb")
@timed
def download_pdb(pdb_id: str, format: str = "pdb",
                 representation: str = "cartoon") -> ToolResult:
    """Download a PDB structure from RCSB PDB and return visualization data."""
    try:
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
        resp = httpx.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return ToolResult.err("download_pdb", f"PDB ID '{pdb_id}' not found at RCSB.")
        resp.raise_for_status()
        pdb_content = resp.text
        # Return both the content (for parse_structure) and the full raw for visualization
        return ToolResult.ok(
            "download_pdb",
            data={
                "pdb_id": pdb_id.upper(),
                "content": pdb_content,
                "format": format,
                "representation": representation,
                "source_url": url,
            },
        )
    except httpx.TimeoutException:
        return ToolResult.err("download_pdb", f"Timeout fetching PDB '{pdb_id}' from RCSB.")
    except httpx.HTTPStatusError as e:
        return ToolResult.err("download_pdb", f"RCSB returned {e.response.status_code} for '{pdb_id}'.")
    except Exception as e:
        return ToolResult.err("download_pdb", str(e), exc_info=sys.exc_info())


@register_tool("parse_structure")
@timed
def parse_structure(file_path: str) -> ToolResult:
    """Parse a PDB/mmCIF file and extract structure information."""
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult.err("parse_structure", f"File not found: {file_path}")
        content = path.read_text()
        lines = [l for l in content.split("\n") if l.startswith("ATOM") or l.startswith("HETATM")]
        if not lines:
            return ToolResult.err("parse_structure", f"No ATOM/HETATM records in {file_path}")
        residues = set()
        atoms = 0
        for l in lines:
            try:
                residues.add(l[22:26].strip())
                atoms += 1
            except IndexError:
                continue
        return ToolResult.ok("parse_structure", data={
            "file": str(path),
            "atoms": atoms,
            "residues": len(residues),
            "chains": len(set(l[21:22] for l in lines if len(l) > 21)),
            "model_count": len([l for l in content.split("\n") if l.startswith("MODEL")]),
            "preview": content[:500],
        })
    except Exception as e:
        return ToolResult.err("parse_structure", str(e), exc_info=sys.exc_info())


@register_tool("search_literature")
@timed
def search_literature(query: str, source: str = "all",
                      max_results: int = 10) -> ToolResult:
    """Search scientific literature (PubMed, arXiv, bioRxiv)."""
    try:
        results = []
        if source in ("pubmed", "all"):
            try:
                esearch = httpx.get(
                    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                    params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
                    headers=HEADERS, timeout=20,
                )
                ids = esearch.json().get("esearchresult", {}).get("idlist", [])
                if ids:
                    efetch = httpx.get(
                        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                        params={"db": "pubmed", "id": ",".join(ids[:5]), "retmode": "xml"},
                        headers=HEADERS, timeout=20,
                    )
                    results.append({"source": "pubmed", "raw": efetch.text[:3000]})
            except Exception as e:
                results.append({"source": "pubmed", "error": str(e)})
        if source in ("arxiv", "all"):
            try:
                resp = httpx.get(
                    "http://export.arxiv.org/api/query",
                    params={"search_query": f"all:{query}", "max_results": max_results},
                    headers=HEADERS, timeout=20,
                )
                results.append({"source": "arxiv", "raw": resp.text[:4000]})
            except Exception as e:
                results.append({"source": "arxiv", "error": str(e)})
        return ToolResult.ok("search_literature", data={
            "query": query, "source": source,
            "num_results": len(results),
            "results": results,
        })
    except Exception as e:
        return ToolResult.err("search_literature", str(e), exc_info=sys.exc_info())


@register_tool("download_tcga_survival")
@timed
def download_tcga_survival(cohort: str,
                           survival_type: str = "overall") -> ToolResult:
    """Download clinical survival data from TCGA via the GDC API."""
    try:
        filters = json.dumps({
            "op": "and",
            "content": [{"op": "in", "content": {"field": "project.project_id", "value": [f"TCGA-{cohort}"]}}],
        })
        resp = httpx.get(
            "https://api.gdc.cancer.gov/cases",
            params={"filters": filters, "size": "1000", "format": "JSON"},
            headers=HEADERS, timeout=30,
        )
        hits = resp.json().get("data", {}).get("hits", [])
        return ToolResult.ok("download_tcga_survival",
                             data={"cohort": cohort, "num_patients": len(hits),
                                   "survival_type": survival_type})
    except httpx.TimeoutException:
        return ToolResult.err("download_tcga_survival", f"GDC API timeout for cohort '{cohort}'.")
    except Exception as e:
        return ToolResult.err("download_tcga_survival", str(e), exc_info=sys.exc_info())


@register_tool("run_bio_pipeline")
@timed
def run_bio_pipeline(command: str, name: str,
                     estimated_duration: str = "unknown") -> ToolResult:
    """Dispatch a long-running bio task to Modal cloud (via biocontainers).
    Returns a job_id immediately. All compute happens on Modal.com — never local.
    """
    job_id = f"job_{int(time.time())}_{os.urandom(4).hex()}"

    # Route to Modal instead of spawning a local subprocess.
    # Modal runs the command in a BioContainer on Modal cloud infrastructure.
    try:
        from storage import get_storage
        get_storage().create_job(
            job_id=job_id, tool="run_bio_pipeline",
            name=name, command=command,
            metadata={"estimated_duration": estimated_duration},
        )
    except Exception as e:
        print(f"[run_bio_pipeline] StorageBackend.create_job failed: {e}")

    # Rehydrate job_type from the command string if possible
    cmd_lower = command.lower()
    if "star" in cmd_lower or "alignment" in cmd_lower:
        job_type = "star_alignment"
    elif "sra" in cmd_lower or "fasterq" in cmd_lower or "prefetch" in cmd_lower:
        job_type = "download_sra"
    elif "deseq2" in cmd_lower or "deseq" in cmd_lower:
        job_type = "deseq2"
    else:
        job_type = "generic"

    # Build Modal params — command is passed as the primary argument
    params: dict[str, Any] = {"command": command}
    if job_type == "star_alignment":
        # Extract sra_accession from command if possible
        import re
        m = re.search(r"(SRR|ERR|DRR)\d+", command)
        if m:
            params["sra_accession"] = m.group(0)
    elif job_type == "deseq2":
        import re
        m = re.search(r"--count-matrix\s+(\S+)", command)
        if m:
            params["count_matrix_path"] = m.group(1)

    # Use background mode so it returns immediately with a job_id
    params["background"] = True
    raw = run_modal_task(job_type, params, workspace=None)

    if isinstance(raw, dict) and raw.get("status") == "detached":
        return ToolResult.ok("run_bio_pipeline",
                             data={"job_id": raw.get("job_id", job_id),
                                   "message": f"Bio task '{name}' dispatched to Modal.",
                                   "call_id": raw.get("message", "")},
                             job_id=raw.get("job_id", job_id))

    # Modal unavailable or dispatch failed
    err_msg = raw.get("error") if isinstance(raw, dict) else str(raw)
    return ToolResult.err("run_bio_pipeline", str(err_msg))


@register_tool("get_job_status")
@timed
def get_job_status(job_id: str) -> ToolResult:
    """Poll a background job status by job_id. Checks SQLite storage, falls back to JSON on filesystem."""
    # Try storage first (primary)
    try:
        from storage import get_storage
        record = get_storage().get_job(job_id)
        if record is not None:
            return ToolResult.ok("get_job_status", data=record)
    except Exception as e:
        pass  # Fall through to filesystem

    # Fallback: filesystem JSON (for jobs started before storage was added)
    workspace = Path(os.environ.get("ESAPIENS_DATA_DIR", "~/esapiens-data")).expanduser()
    job_path = workspace / "background_jobs" / f"{job_id}.json"
    if not job_path.exists():
        return ToolResult.err("get_job_status", f"Job '{job_id}' not found. No record in storage or at '{job_path}'.")
    try:
        status_data = json.loads(job_path.read_text())
        return ToolResult.ok("get_job_status", data=status_data)
    except json.JSONDecodeError as e:
        return ToolResult.err("get_job_status", f"Corrupt job file for '{job_id}': {e}")
    except Exception as e:
        return ToolResult.err("get_job_status", str(e), exc_info=sys.exc_info())


@register_tool("run_python_plot")
@timed
def run_python_plot(code: str, title: str = "", pretty: bool = True) -> ToolResult:
    """Generate a matplotlib/seaborn plot. Returns a base64 PNG embedded in a data URI."""
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    try:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt, seaborn as sns
        plt.close('all')
        exec(compile(code.strip("`").replace("python", "", 1), "<run_python_plot>", "exec"), {
            "__builtins__": _SAFE_BUILTINS,
            "plt": plt, "sns": sns,
            "np": __import__('numpy'), "pd": __import__('pandas'),
            "WORKSPACE": WORKSPACE, "os": _safe_os,
        })
        fig = plt.gcf()
        if not fig.axes:
            return ToolResult.err("run_python_plot", "No axes generated. Check your plotting code.")
        buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=150); b64 = base64.b64encode(buf.getvalue()).decode()
        plt.close('all')
        return ToolResult.ok("run_python_plot",
                             data={"type": "image", "image": f"data:image/png;base64,{b64}", "title": title})
    except Exception as e:
        return ToolResult.err("run_python_plot", str(e), exc_info=sys.exc_info())


@register_tool("plotly_plot")
@timed
def plotly_plot(code: str, title: str = "Plot") -> ToolResult:
    """Generate an interactive Plotly chart. Returns an HTML document with CDN-hosted Plotly.js."""
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    try:
        import plotly.express as px
        ns = {"__builtins__": _SAFE_BUILTINS, "px": px, "np": __import__('numpy'), "pd": __import__('pandas'), "WORKSPACE": WORKSPACE}
        exec(compile(code.strip("`").replace("python", "", 1), "<plotly>", "exec"), ns)
        fig = ns.get("fig")
        if not fig:
            return ToolResult.err("plotly_plot", "No 'fig' object found. Return fig from your code.")
        html = fig.to_html(include_plotlyjs='cdn', full_html=False)
        return ToolResult.ok("plotly_plot",
                             data={"type": "plotly", "html": html, "title": title})
    except Exception as e:
        return ToolResult.err("plotly_plot", str(e), exc_info=sys.exc_info())


@register_tool("execute_python")
@timed
def execute_python(code: str, description: str = "") -> ToolResult:
    """Execute lightweight Python code on the VPS. For data manipulation, simple stats,
    file I/O, and quick lookups ONLY. NOT for bioinformatics computation.

    PROHIBITED on VPS:
      - Running STAR, DESeq2, SRA downloads, alignment, or any bio tool
      - pip installing bio packages (biopython, scanpy, anndata, etc.)
      - Downloading large datasets (>10MB)
      - Long-running computations (>30s CPU time)
    Use run_bio_pipeline or run_modal_job for heavy or bio workloads.
    """
    # ── Bio computation guard: refuse bio tool usage that belongs on Modal ──
    BIO_PATTERNS = [
        # Bio tool commands
        r'\bSTAR\b', r'\bfasterq-dump\b', r'\bprefetch\b', r'\bsratoolkit\b',
        r'\bRscript\b.*DESeq', r'\bRscript\b.*\bdeseq\b',
        r'\bsamtools\b', r'\bbcftools\b', r'\bbwa\b', r'\bbowtie2?\b',
        r'\bhtseq-count\b', r'\bfeatureCounts\b', r'\bfastqc\b',
        r'\btrimmomatic\b', r'\bcutadapt\b', r'\bmultiqc\b',
        r'\bkallisto\b', r'\bsalmon\b', r'\bhisat2\b',
        # Heavy bio Python imports
        r'\bimport\s+scanpy\b', r'\bimport\s+anndata\b', r'\bfrom\s+scanpy\b',
        r'\bimport\s+biopython\b', r'\bfrom\s+Bio\b', r'\bimport\s+Bio\b',
        r'\bimport\s+pybedtools\b', r'\bimport\s+pysam\b', r'\bfrom\s+pysam\b',
        r'\bimport\s+deeptools\b', r'\bfrom\s+deeptools\b',
        # Heavy compute patterns
        r'\bsubprocess\.(run|call|Popen)\b.*\b(star|deseq|sra|fasterq|prefetch|samtools|bwa|bowtie)\b',
        # Shell injection via os
        r'\bos\.system\b', r'\bos\.popen\b', r'\bos\.exec\b',
        # Large data download patterns
        r'\bftp://\b.*\b(sra|gb|gds)\b',
        r'\bhttps?://ftp\.ncbi\.nlm\.nih\.gov/',
        r'\bSRA.*download\b', r'\bdownload.*SRR\b',
    ]
    import re as _re
    for pattern in BIO_PATTERNS:
        if _re.search(pattern, code, _re.IGNORECASE):
            return ToolResult.err(
                "execute_python",
                "Bioinformatics computation is NOT allowed on VPS. "
                "Dispatch to Modal using run_bio_pipeline instead. "
                "Example: run_bio_pipeline(command='<your command>', name='<task name>')"
            )

    # ── VPS-safe Python sandbox ──
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    ns = {"__builtins__": _SAFE_BUILTINS, "os": _safe_os, "np": __import__('numpy', fromlist=['']),
          "pd": __import__('pandas', fromlist=['']), "WORKSPACE": WORKSPACE}
    try:
        exec(compile(code.strip("`").replace("python", "", 1), "<exec>", "exec"), ns)
        return ToolResult.ok("execute_python", data={"description": description or "code executed"})
    except Exception as e:
        return ToolResult.err("execute_python", str(e), exc_info=sys.exc_info())


# ── Modal dispatch ────────────────────────────────────────────────────────────

from modal_tasks import MODAL_AVAILABLE, BIO_TASKS, run_modal_task, create_modal_task, get_available_tasks  # noqa: E402


@register_tool("run_modal_job")
@timed
def run_modal_job(job_type: str, params: dict, background: bool = False) -> ToolResult:
    """Dispatch a heavy compute task (STAR, DESeq2, SRA download) to a Modal BioContainer."""
    if not MODAL_AVAILABLE:
        return ToolResult.err("run_modal_job", "Modal SDK not installed or not importable.")
    if job_type not in BIO_TASKS:
        return ToolResult.err("run_modal_job", f"Unknown job_type '{job_type}'. Available: {list(BIO_TASKS.keys())}")
    workspace = Path(os.environ.get("ESAPIENS_DATA_DIR", "~/esapiens-data")).expanduser()
    if background:
        params["background"] = True
    raw = run_modal_task(job_type, params, workspace=workspace)
    # Wrap Modal's raw dict response in a ToolResult
    if isinstance(raw, dict) and "error" in raw:
        return ToolResult.err("run_modal_job", raw["error"])
    return ToolResult.ok("run_modal_job", data=raw)


@register_tool("create_modal_tool")
@timed
def create_modal_tool_handler(**kwargs) -> ToolResult:
    """Dynamically create a new Modal BioContainer task at runtime."""
    return create_modal_tool(**kwargs)


# ── Dynamic tools ──────────────────────────────────────────────────────────────

from dynamic_tools import create_tool as _create_tool_impl, load_dynamic_tools as _load_dynamic_tools  # noqa: E402


@register_tool("create_tool")
@timed
def create_tool_handler(**kwargs) -> ToolResult:
    """Create a new VPS-level tool at runtime. Useful when a capability is missing."""
    return _create_tool_impl(**kwargs)


# ── Tool execution dispatcher ──────────────────────────────────────────────────


def execute_tool(name: str, args: dict) -> str:
    """Dispatch a named tool with given args. Returns JSON string for the LLM tool_obs node."""
    if name not in TOOL_IMPLS:
        err = ToolResult.err("execute_tool", f"Unknown tool: '{name}'. Available: {list(TOOL_IMPLS.keys())}")
        return json.dumps(err.to_dict(), default=str)
    try:
        result = TOOL_IMPLS[name](**args)
        if isinstance(result, ToolResult):
            return json.dumps(result.to_dict(), default=str)
        # Backward compat: raw dict returned — wrap it
        return json.dumps({"tool": name, "status": "success", "data": result}, default=str)
    except Exception as e:
        err = ToolResult.err("execute_tool", str(e), exc_info=sys.exc_info())
        return json.dumps(err.to_dict(), default=str)


# ── Module init: load persistent dynamic tools ────────────────────────────────
# Must never crash the agent at startup. Failures are logged, not silently swallowed.

_dyn_load_errors: list[str] = []
try:
    loaded = _load_dynamic_tools()
    if loaded:
        print(f"[tools] Initialized {len(loaded)} persistent dynamic tools: {[t['name'] for t in loaded]}")
except Exception as e:
    print(f"[tools] DYNAMIC TOOL LOADER FAILED on startup: {e}")
    print(f"[tools] Agent will continue.")