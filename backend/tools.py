"""
Bioinformatics Tools — ported from Sprint-1.

Provides JSON-schema tool definitions and corresponding Python functions
for LangGraph tool-callable nodes.
"""

from typing import Any, Optional
import os
import json
import httpx
import subprocess
import sys
import tempfile
import base64
import textwrap
import io
import types
import threading
import time
from pathlib import Path

# Shared HTTP headers for NCBI/GDC API compliance
HEADERS = {"User-Agent": "E.sapiens/1.0 (contact: research@example.edu); research assistant"}

# ═══════════════════════════════════════════════════════════════════════════
# Secret Hygiene — prevent agent code-exec tools from leaking API keys
# ═══════════════════════════════════════════════════════════════════════════

_SECRET_ENV_VARS = {
    "OPENROUTER_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "JWT_SECRET",
}


def _make_safe_os():
    """Create an os-like module that masks secrets in os.environ."""
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

# =============================================================================
# Tool definitions
# =============================================================================

TOOL_DEFINITIONS: list = [
    {
        "name": "download_pdb",
        "description": "Download a PDB structure from RCSB PDB and return visualization data for 3D rendering. Use this when the user asks to show, view, visualize, or analyze a PDB structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "pdb_id": {"type": "string", "description": "4-character PDB ID (e.g., '1ABC')"},
                "format": {"type": "string", "enum": ["mmCif", "pdb", "cif"], "default": "pdb"},
                "representation": {"type": "string", "enum": ["cartoon", "ball+stick", "surface", "licorice", "backbone", "spacefill"], "default": "cartoon"},
            },
            "required": ["pdb_id"],
        },
    },
    {
        "name": "parse_structure",
        "description": "Parse a PDB/mmCIF file and extract structure information.",
        "parameters": {
            "type": "object",
            "properties": {"file_path": {"type": "string"}},
            "required": ["file_path"],
        },
    },
    {
        "name": "search_literature",
        "description": "Search scientific literature (PubMed, arXiv, bioRxiv).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "source": {"type": "string", "enum": ["pubmed", "arxiv", "biorxiv", "all"], "default": "all"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "download_tcga_survival",
        "description": "Download clinical survival data from TCGA via the GDC API.",
        "parameters": {
            "type": "object",
            "properties": {
                "cohort": {"type": "string", "description": "TCGA cohort (e.g., BRCA, LUAD)"},
                "survival_type": {"type": "string", "enum": ["overall", "disease_free"], "default": "overall"},
            },
            "required": ["cohort"],
        },
    },
    {
        "name": "run_bio_pipeline",
        "description": "Run long-running bioinformatics pipelines (Variant Calling, MD Simulations, BWA-MEM) in detached mode on the VPS. Returns immediately with a job ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "name": {"type": "string", "description": "Descriptive name for the job"},
                "estimated_duration": {"type": "string", "description": "Human readable estimate (e.g. '2 hours')"},
            },
            "required": ["command", "name"],
        },
    },
    {
        "name": "run_python_plot",
        "description": "Execute Python plotting code and return image.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "title": {"type": "string"},
                "pretty": {"type": "boolean", "description": "Apply publication-quality styling (enabled by default)"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "plotly_plot",
        "description": "Create interactive Plotly plots.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "create_tool",
        "description": "Create a new tool that will be available for future queries.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "parameters": {"type": "object", "properties": {}},
                "code": {"type": "string"},
            },
            "required": ["name", "description", "parameters", "code"],
        },
    },
    {
        "name": "run_modal_job",
        "description": "Execute a bioinformatics task on Modal's serverless cloud. Supports background: true for detached execution.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_type": {"type": "string", "enum": ["star_alignment", "download_sra", "deseq2"]},
                "params": {"type": "object"},
                "background": {"type": "boolean", "description": "Set to true to run in detached mode"},
            },
            "required": ["job_type", "params"],
        },
    },
    {
        "name": "create_modal_tool",
        "description": "Create a new Modal serverless task dynamically.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "parameters": {"type": "object", "properties": {}},
                "code": {"type": "string"},
                "cpu": {"type": "number", "default": 2.0},
                "memory_mb": {"type": "integer", "default": 4096},
                "image_packages": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "description", "parameters", "code"],
        },
    },
    {
        "name": "execute_python",
        "description": "Execute arbitrary Python code.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["code"],
        },
    },
]

# =============================================================================
# Tool implementations
# =============================================================================

TOOL_IMPLS: dict[str, callable] = {}

def register_tool(name: str):
    def decorator(func):
        TOOL_IMPLS[name] = func
        return func
    return decorator


@register_tool("download_pdb")
def download_pdb(pdb_id: str, format: str = "pdb", representation: str = "cartoon") -> dict:
    valid_representations = {"cartoon", "ball+stick", "surface", "licorice", "backbone", "spacefill"}
    if representation not in valid_representations: representation = "cartoon"
    pdb_id = pdb_id.lower().strip()
    check_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        resp = httpx.head(check_url, timeout=10, follow_redirects=True, headers=HEADERS)
        if resp.status_code != 200:
            return {"tool": "download_pdb", "error": f"PDB {pdb_id} not found."}
    except Exception as e: return {"error": str(e)}
    return {
        "tool": "download_pdb", "pdb_id": pdb_id,
        "visualization": {"type": "structure", "pdb_id": pdb_id, "representation": representation, "title": f"PDB: {pdb_id.upper()}"}
    }


@register_tool("parse_structure")
def parse_structure(file_path: str) -> dict:
    return {"result": "Structure parsing not implemented."}


@register_tool("search_literature")
def search_literature(query: str, source: str = "all", max_results: int = 10) -> dict:
    max_results = min(max(1, max_results), 50)
    results = []
    errors = []
    if source in ("pubmed", "all"):
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {"db": "pubmed", "term": query, "retmax": str(max_results), "retmode": "json"}
            resp = httpx.get(search_url, params=params, timeout=15, headers=HEADERS)
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
            if ids:
                summ_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                s_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
                resp2 = httpx.get(summ_url, params=s_params, timeout=15, headers=HEADERS)
                data = resp2.json().get("result", {})
                for pmid in ids:
                    info = data.get(pmid, {})
                    if info: results.append({"source": "PubMed", "title": info.get("title", ""), "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
        except Exception as e: errors.append(f"PubMed: {e}")
    if source in ("arxiv", "all"):
        try:
            resp = httpx.get("http://export.arxiv.org/api/query", params={"search_query": f"all:{query}", "max_results": str(max_results)}, timeout=15)
            import re
            entries = re.findall(r'<entry>(.*?)</entry>', resp.text, re.DOTALL)
            for entry in entries:
                t = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                url = re.search(r'<id>http://arxiv.org/abs/(.*?)</id>', entry)
                if t: results.append({"source": "arXiv", "title": t.group(1).strip().replace("\n", " "), "url": f"https://arxiv.org/abs/{url.group(1)}" if url else ""})
        except Exception as e: errors.append(f"arXiv: {e}")
    return {"tool": "search_literature", "results": results[:max_results], "errors": errors if errors else None}


@register_tool("download_tcga_survival")
def download_tcga_survival(cohort: str, survival_type: str = "overall") -> dict:
    cohort = cohort.upper().strip()
    try:
        resp = httpx.get("https://api.gdc.cancer.gov/cases", params={"filters": json.dumps({"op": "and", "content": [{"op": "in", "content": {"field": "project.project_id", "value": [f"TCGA-{cohort}"]}}]}), "size": "1000", "format": "JSON"}, headers=HEADERS)
        hits = resp.json().get("data", {}).get("hits", [])
        return {"tool": "download_tcga_survival", "cohort": cohort, "num_patients": len(hits), "status": "success"}
    except Exception as e: return {"error": str(e)}


@register_tool("run_bio_pipeline")
def run_bio_pipeline(command: str, name: str, estimated_duration: str = "unknown", **kwargs) -> dict:
    job_id = f"job_{int(time.time())}_{os.urandom(4).hex()}"
    workspace = kwargs.get("WORKSPACE") or Path(os.environ.get("ESAPIENS_DATA_DIR", "~/esapiens-data")).expanduser()
    jobs_dir = workspace / "background_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    job_path, log_path = jobs_dir / f"{job_id}.json", jobs_dir / f"{job_id}.log"
    status_data = {"job_id": job_id, "name": name, "command": command, "status": "running", "start_time": time.time(), "log_path": str(log_path)}
    job_path.write_text(json.dumps(status_data))
    def _run():
        try:
            with open(log_path, "w") as log:
                p = subprocess.Popen(command, shell=True, stdout=log, stderr=log, preexec_fn=os.setsid)
                p.wait()
                status_data.update({"status": "completed" if p.returncode == 0 else "failed", "end_time": time.time(), "exit_code": p.returncode})
                job_path.write_text(json.dumps(status_data))
        except Exception as e:
            status_data.update({"status": "failed", "error": str(e)})
            job_path.write_text(json.dumps(status_data))
    threading.Thread(target=_run, daemon=True).start()
    return {"tool": "run_bio_pipeline", "job_id": job_id, "status": "detached", "message": f"Pipeline '{name}' started."}


@register_tool("run_python_plot")
def run_python_plot(code: str, title: str = "", pretty: bool = True) -> dict:
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; import seaborn as sns
        plt.close('all'); exec(compile(code.strip("`").replace("python", "", 1), "<run_python_plot>", "exec"), {"plt": plt, "sns": sns, "np": __import__('numpy'), "pd": __import__('pandas'), "WORKSPACE": WORKSPACE, "os": _safe_os})
        fig = plt.gcf()
        if fig.axes:
            buf = io.BytesIO(); fig.savefig(buf, format='png'); b64 = base64.b64encode(buf.getvalue()).decode()
            plt.close('all')
            return {"tool": "run_python_plot", "visualization": {"type": "image", "image": "data:image/png;base64," + b64, "title": title}}
        return {"error": "No plot generated."}
    except Exception as e: return {"error": str(e)}


@register_tool("plotly_plot")
def plotly_plot(code: str, title: str = "Plot") -> dict:
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    try:
        import plotly.express as px; ns = {"px": px, "np": __import__('numpy'), "pd": __import__('pandas'), "WORKSPACE": WORKSPACE}
        exec(compile(code.strip("`").replace("python", "", 1), "<plotly>", "exec"), ns)
        fig = ns.get("fig")
        if fig: return {"tool": "plotly_plot", "visualization": {"type": "plotly", "html": fig.to_html(include_plotlyjs='cdn'), "title": title}}
        return {"error": "No 'fig' object."}
    except Exception as e: return {"error": str(e)}


from modal_tasks import MODAL_AVAILABLE, BIO_TASKS, run_modal_task, create_modal_task, get_available_tasks

@register_tool("run_modal_job")
def run_modal_job(job_type: str, params: dict, background: bool = False) -> dict:
    workspace = Path(os.environ.get("ESAPIENS_DATA_DIR", "~/esapiens-data")).expanduser()
    if background: params["background"] = True
    result = run_modal_task(job_type, params, workspace=workspace)
    result["tool"] = "run_modal_job"
    return result

@register_tool("create_modal_tool")
def create_modal_tool_handler(**kwargs):
    return create_modal_task(**kwargs)

def execute_tool(name: str, args: dict) -> str:
    if name not in TOOL_IMPLS: return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        res = TOOL_IMPLS[name](**args)
        return json.dumps(res, default=str)
    except Exception as e: return json.dumps({"error": str(e)})

from dynamic_tools import create_tool as _create_tool_impl, load_dynamic_tools as _load_dynamic_tools

@register_tool("create_tool")
def create_tool_handler(**kwargs): return _create_tool_impl(**kwargs)

@register_tool("execute_python")
def execute_python(code: str, description: str = "") -> dict:
    WORKSPACE = Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))
    ns = {"os": _safe_os, "np": __import__('numpy', fromlist=['']), "pd": __import__('pandas', fromlist=['']), "WORKSPACE": WORKSPACE}
    try:
        exec(compile(code.strip("`").replace("python", "", 1), "<exec>", "exec"), ns)
        return {"tool": "execute_python", "status": "success"}
    except Exception as e: return {"error": str(e)}

try:
    _load_dynamic_tools()
except: pass
