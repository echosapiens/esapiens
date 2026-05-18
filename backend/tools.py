"""
Bioinformatics Tools — ported from Sprint-1.

Provides JSON-schema tool definitions and corresponding Python functions
for LangGraph tool-callable nodes.
"""

from typing import Any
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

# Shared HTTP headers for NCBI/GDC API compliance
HEADERS = {"User-Agent": "E.sapiens/1.0 (contact: research@example.edu); research assistant"}

# ═══════════════════════════════════════════════════════════════════════════
# Secret Hygiene — prevent agent code-exec tools from leaking API keys
# ═══════════════════════════════════════════════════════════════════════════
# Tools that exec() user-provided Python (execute_python, run_python_plot,
# plotly_plot) pass `os` to the sandbox — giving agent code access to
# os.environ and all secrets. We create a _safe_os proxy that exposes
# all os attributes EXCEPT environ, which is replaces with a filtered
# copy that strips sensitive keys.

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
    # Create a filtered environ that hides secrets
    _safe_environ = types.MappingProxyType({
        k: ("***REDACTED***" if k in _SECRET_ENV_VARS else v)
        for k, v in _os.environ.items()
    })
    safe = types.ModuleType("os_safe")
    # Copy all attributes from the real os module
    for attr in dir(_os):
        if attr == "environ":
            continue  # skip real environ
        try:
            setattr(safe, attr, getattr(_os, attr))
        except (AttributeError, TypeError):
            pass
    # Replace with redacted environ
    safe.environ = _safe_environ
    # Also shadow getenv to prevent bypassing the proxy
    safe.getenv = lambda key, default=None: _safe_environ.get(key, default)
    return safe


_safe_os = _make_safe_os()

# =============================================================================
# Tool definitions (OpenAI-compatible JSON schema for function calling)
# =============================================================================

TOOL_DEFINITIONS: list = [
    # ------------------------------------------------------------------
    # Structural biology
    # ------------------------------------------------------------------
    {
        "name": "download_pdb",
        "description": "Download a PDB structure from RCSB PDB and return visualization data for 3D rendering. Use this when the user asks to show, view, visualize, or analyze a PDB structure. Returns structure data that triggers the NGL 3D viewer in the frontend. The representation parameter controls how the structure is initially displayed — the user can also switch representations interactively in the viewer.",
        "parameters": {
            "type": "object",
            "properties": {
                "pdb_id": {
                    "type": "string",
                    "description": "4-character PDB ID (e.g., '1ABC', '3FHB')",
                },
                "format": {
                    "type": "string",
                    "enum": ["mmCif", "pdb", "cif"],
                    "description": "File format to download",
                    "default": "pdb",
                },
                "representation": {
                    "type": "string",
                    "enum": ["cartoon", "ball+stick", "surface", "licorice", "backbone", "spacefill"],
                    "description": "Initial visual representation for the 3D viewer. Use 'surface' for solvent-accessible surface, 'cartoon' for secondary structure overview, 'ball+stick' for atomic detail, 'spacefill' for van der Waals spheres.",
                    "default": "cartoon",
                },
            },
            "required": ["pdb_id"],
        },
    },
    {
        "name": "parse_structure",
        "description": "Parse a PDB/mmCIF file and extract structure information.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the PDB/mmCIF file",
                },
            },
            "required": ["file_path"],
        },
    },
    # ------------------------------------------------------------------
    # Literature search
    # ------------------------------------------------------------------
    {
        "name": "search_literature",
        "description": "Search scientific literature (PubMed, arXiv, bioRxiv, Google Scholar). Returns titles, abstracts, URLs, and citation info. Use for finding papers, citations, or research background.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "source": {
                    "type": "string",
                    "enum": ["pubmed", "arxiv", "biorxiv", "google_scholar", "all"],
                    "default": "all",
                },
                "max_results": {
                    "type": "integer",
                    "default": 10,
                },
            },
        "required": ["query"],
        },
    },
    # ------------------------------------------------------------------
    # TCGA clinical data
    # ------------------------------------------------------------------
    {
        "name": "download_tcga_survival",
        "description": "Download clinical survival data from TCGA via the GDC API. Returns patient-level time and event data for Kaplan-Meier analysis. Supports overall survival (OS) and disease-free survival (DFS).",
        "parameters": {
            "type": "object",
            "properties": {
                "cohort": {
                    "type": "string",
                    "description": "TCGA cohort abbreviation (e.g., BRCA, LUAD, COAD, GBM, KIRC)",
                },
                "survival_type": {
                    "type": "string",
                    "enum": ["overall", "disease_free"],
                    "default": "overall",
                    "description": "'overall' for overall survival (OS), 'disease_free' for disease-free survival (DFS)",
                },
            },
            "required": ["cohort"],
        },
    },
    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------
    {
        "name": "run_python_plot",
        "description": "Execute Python plotting code using matplotlib/seaborn/plotly and return the rendered image. Use this for ALL plotting needs — line charts, scatter, bar, heatmaps, distributions, etc. Supports matplotlib, seaborn, and plotly. Returns the plot as an image. Set pretty=True for publication-quality aesthetics. MANDATORY: Only plot real-world data downloaded via tools or execute_python. NEVER use synthetic, mock, or example data.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code that creates a plot. Libraries available: plt (matplotlib), sns (seaborn), px/pgo (plotly), np (numpy), pd (pandas). Do NOT call plt.show().",
                },
                "title": {
                    "type": "string",
                    "description": "Title of the plot",
                },
                "pretty": {
                    "type": "boolean",
                    "description": "Apply publication-quality styling (enabled by default)",
                },
            },
            "required": ["code"],
        },
    },
    # ------------------------------------------------------------------
    # Plotly interactive plots
    # ------------------------------------------------------------------
    {
        "name": "plotly_plot",
        "description": "Create interactive Plotly plots (even better than static matplotlib). Returns an interactive HTML visualization. Use for complex interactive visualizations, 3D plots, or when user wants 'better' plots. Supports plotly.express and plotly.graph_objects. MANDATORY: Only plot real-world data downloaded via tools or execute_python. NEVER use synthetic, mock, or example data.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Plotly code using px (plotly.express) or go (graph_objects). Returns interactive HTML.",
                },
                "title": {
                    "type": "string",
                    "description": "Plot title",
                },
            },
            "required": ["code"],
        },
    },
    # ------------------------------------------------------------------
    # Dynamic tool creation
    # ------------------------------------------------------------------
    {
        "name": "create_tool",
        "description": "Create a new tool that will be available for future queries. Use this when you encounter a task that requires a capability you do not currently have (downloading datasets from GEO, ArrayExpress, SRA, etc.). The tool code runs in Python with access to httpx, subprocess, json, os, Path, and other standard libraries. Created tools persist across sessions. MANDATORY: Dynamic tools must focus on real-world data retrieval and analysis. NEVER generate synthetic or mock data.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Tool name, lowercase with underscores (e.g. 'download_geo', 'fetch_sra')",
                },
                "description": {
                    "type": "string",
                    "description": "Clear description of what the tool does",
                },
                "parameters": {
                    "type": "object",
                    "description": "JSON schema for the tool's parameters",
                    "properties": {},
                },
                "code": {
                    "type": "string",
                    "description": "Python function body (indented code under the function definition). Receives parameters as kwargs. Must return a dict. Available imports: os, json, httpx, subprocess, sys, tempfile, base64, io, textwrap, Path.",
                },
            },
            "required": ["name", "description", "parameters", "code"],
        },
    },
    # ------------------------------------------------------------------
    # Modal serverless jobs
    # ------------------------------------------------------------------
    {
        "name": "run_modal_job",
        "description": "Execute a pre-defined bioinformatics task on Modal's serverless cloud infrastructure with high-CPU/high-RAM containers. Available job types: 'star_alignment' (STAR RNA-seq alignment, 32 cores/128GB), 'download_sra' (SRA FASTQ download), 'deseq2' (DESeq2 differential expression). Use this for computationally heavy tasks that exceed local resources. Results are returned as structured data.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_type": {
                    "type": "string",
                    "enum": ["star_alignment", "download_sra", "deseq2"],
                    "description": "Type of bioinformatics job to run on Modal",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters for the job. Varies by job_type. star_alignment: {sra_accession, gencode_version, star_index_path}. download_sra: {sra_accession, format}. deseq2: {count_matrix_path, design_formula, contrast}.",
                },
            },
            "required": ["job_type", "params"],
        },
    },
    {
        "name": "create_modal_tool",
        "description": "Create a new Modal serverless task for heavy compute that the agent can run on-demand. Define the Python code, resource requirements (CPU, memory, GPU), and packages needed. The task runs on Modal's cloud infrastructure. Use this when existing Modal jobs don't cover a needed computation (e.g., custom ML inference, batch genome processing).",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Task name, lowercase with underscores (e.g. 'custom_star_index')",
                },
                "description": {
                    "type": "string",
                    "description": "What this task does",
                },
                "parameters": {
                    "type": "object",
                    "description": "JSON schema for the task's parameters",
                    "properties": {},
                },
                "code": {
                    "type": "string",
                    "description": "Python function body. Available: standard library, plus pip/apk packages specified in image_packages/image_apt_packages. Must return a dict. Access parameters as function arguments.",
                },
                "cpu": {
                    "type": "number",
                    "description": "Number of CPU cores (default 2)",
                    "default": 2,
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Memory in MB (default 4096)",
                    "default": 4096,
                },
                "gpu": {
                    "type": "string",
                    "description": "GPU type: 'T4', 'A10', 'L4', 'A100-40GB', 'A100-80GB', 'H100'. Omit for CPU-only.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 3600)",
                    "default": 3600,
                },
                "image_packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "pip packages to install in the container (e.g. ['scanpy', 'anndata'])",
                },
                "image_apt_packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "apt packages to install (e.g. ['samtools', 'bedtools'])",
                },
            },
            "required": ["name", "description", "parameters", "code"],
        },
    },
    # ------------------------------------------------------------------
    # General Python execution
    # ------------------------------------------------------------------
    {
        "name": "execute_python",
        "description": "Execute arbitrary Python code for data analysis, file processing, or any computation. Use when existing tools are insufficient — downloading datasets, processing files, running bioinformatics pipelines, etc. Libraries available: pandas, numpy, scipy, matplotlib, seaborn, httpx, biopython (Bio), os, json, subprocess, Path. Write results to files in the workspace directory (available as WORKSPACE path). For plots, use run_python_plot or plotly_plot instead. MANDATORY: Only process real-world data. NEVER use synthetic, mock, or example data.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute. Results printed to stdout are captured. Use WORKSPACE variable for file paths.",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of what this code does (for logging)",
                },
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
    """Decorator to register a tool implementation."""
    def decorator(func):
        TOOL_IMPLS[name] = func
        return func
    return decorator


@register_tool("download_pdb")
def download_pdb(pdb_id: str, format: str = "pdb", representation: str = "cartoon") -> dict:
    """Download PDB structure from RCSB and return visualization data.

    Args:
        pdb_id: PDB identifier (e.g. '1TUP', '6LU7')
        format: File format (pdb or cif)
        representation: Visual representation mode. One of:
            cartoon, ball+stick, surface, licorice, backbone, spacefill
    """
    valid_representations = {"cartoon", "ball+stick", "surface", "licorice", "backbone", "spacefill"}
    if representation not in valid_representations:
        representation = "cartoon"

    pdb_id = pdb_id.lower().strip()
    
    # Verify PDB exists by checking RCSB
    check_url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        resp = httpx.head(check_url, timeout=10, follow_redirects=True, headers=HEADERS)
        if resp.status_code != 200:
            return {
                "tool": "download_pdb",
                "pdb_id": pdb_id,
                "result": f"Error: PDB {pdb_id} not found on RCSB (status {resp.status_code})",
            }
    except Exception as e:
        return {
            "tool": "download_pdb",
            "pdb_id": pdb_id,
            "result": f"Error checking PDB: {e}",
        }
    
    return {
        "tool": "download_pdb",
        "pdb_id": pdb_id,
        "visualization": {
            "type": "structure",
            "pdb_id": pdb_id,
            "representation": representation,
            "title": f"PDB: {pdb_id.upper()}",
        },
    }


@register_tool("parse_structure")
def parse_structure(file_path: str) -> dict:
    """Parse a PDB/mmCIF file and extract structure information."""
    return {
        "tool": "parse_structure",
        "file_path": file_path,
        "result": "Structure parsing not yet implemented in this sprint.",
    }


@register_tool("search_literature")
def search_literature(query: str, source: str = "all", max_results: int = 10) -> dict:
    """Search scientific literature across PubMed, arXiv, and bioRxiv.
    
    Args:
        query: Search terms (supports Boolean: AND, OR, NOT)
        source: Which source to search — 'pubmed', 'arxiv', 'biorxiv', or 'all'
        max_results: Maximum number of results to return (1-50)
    """
    max_results = min(max(1, max_results), 50)
    results = []
    errors = []
    
    # ── PubMed via NCBI E-utilities ──
    if source in ("pubmed", "all"):
        try:
            # Step 1: Search → get PMIDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": str(max_results),
                "retmode": "json",
                "sort": "relevance",
            }
            resp = httpx.get(search_url, params=search_params, timeout=15, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
            search_data = resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            
            if id_list:
                # Step 2: Fetch summaries
                summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                summary_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                }
                resp2 = httpx.get(summary_url, params=summary_params, timeout=15, follow_redirects=True, headers=HEADERS)
                resp2.raise_for_status()
                summary_data = resp2.json()
                
                for pmid in id_list:
                    info = summary_data.get("result", {}).get(pmid, {})
                    if info:
                        authors = [a.get("name", "") for a in info.get("authors", [])[:3]]
                        results.append({
                            "source": "PubMed",
                            "title": info.get("title", ""),
                            "authors": ", ".join(authors) + (" et al." if len(info.get("authors", [])) > 3 else ""),
                            "journal": info.get("fulljournalname", info.get("source", "")),
                            "year": info.get("pubdate", "")[:4],
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            "pmid": pmid,
                        })
        except Exception as e:
            errors.append(f"PubMed: {e}")
    
    # ── arXiv ──
    if source in ("arxiv", "all"):
        try:
            arxiv_url = "http://export.arxiv.org/api/query"
            arxiv_params = {
                "search_query": f"all:{query}",
                "start": "0",
                "max_results": str(max_results),
                "sortBy": "relevance",
            }
            resp = httpx.get(arxiv_url, params=arxiv_params, timeout=15, follow_redirects=True, headers=HEADERS)
            resp.raise_for_status()
            
            # Parse XML manually (no dependency needed)
            import re
            entries = re.findall(r'<entry>(.*?)</entry>', resp.text, re.DOTALL)
            for entry in entries[:max_results]:
                title = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
                summary = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
                authors = re.findall(r'<name>(.*?)</name>', entry)
                arxiv_id = re.search(r'<id>http://arxiv.org/abs/(.*?)</id>', entry)
                published = re.search(r'<published>(.*?)</published>', entry)
                
                results.append({
                    "source": "arXiv",
                    "title": title.group(1).strip().replace("\n", " ") if title else "",
                    "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                    "journal": "arXiv",
                    "year": published.group(1)[:4] if published else "",
                    "url": f"https://arxiv.org/abs/{arxiv_id.group(1)}" if arxiv_id else "",
                    "abstract": summary.group(1).strip().replace("\n", " ")[:300] if summary else "",
                })
        except Exception as e:
            errors.append(f"arXiv: {e}")
    
    # ── bioRxiv ──
    if source in ("biorxiv", "all"):
        try:
            biorxiv_url = "https://api.biorxiv.org/details/biorxiv"
            biorxiv_params = {
                "term": query,
                "limit": str(max_results),
            }
            resp = httpx.get(biorxiv_url, params=biorxiv_params, timeout=15, follow_redirects=True, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                papers = data.get("collection", [])[:max_results]
                for paper in papers:
                    results.append({
                        "source": "bioRxiv",
                        "title": paper.get("title", ""),
                        "authors": paper.get("authors", ""),
                        "journal": "bioRxiv",
                        "year": paper.get("date", "")[:4],
                        "url": f"https://doi.org/{paper['doi']}" if paper.get("doi") else f"https://www.biorxiv.org/content/{paper.get('doi', '')}",
                        "doi": paper.get("doi", ""),
                    })
        except Exception as e:
            errors.append(f"bioRxiv: {e}")
    
    # Trim to max_results total
    results = results[:max_results]
    
    return {
        "tool": "search_literature",
        "query": query,
        "source": source,
        "total_results": len(results),
        "results": results,
        "errors": errors if errors else None,
    }


@register_tool("download_tcga_survival")
def download_tcga_survival(cohort: str, survival_type: str = "overall") -> dict:
    """Download clinical survival data from TCGA via GDC API.

    Args:
        cohort: TCGA cohort abbreviation (e.g., 'BRCA', 'LUAD', 'COAD', 'GBM')
        survival_type: 'overall' for overall survival (OS), 'disease_free' for disease-free survival (DFS)
    """
    import httpx

    # Normalize cohort name
    cohort = cohort.upper().strip()

    # Map survival type to GDC fields
    if survival_type == "disease_free":
        time_field = "days_to_new_tumor_event_after_initial_treatment"
        event_field = "new_tumor_event_after_initial_treatment"
    else:
        time_field = "days_to_death"
        event_field = "vital_status"

    # Query GDC API for clinical data
    gdc_url = "https://api.gdc.cancer.gov/cases"
    filters = {
        "op": "and",
        "content": [
            {"op": "in", "content": {"field": "project.project_id", "value": [f"TCGA-{cohort}"]}},
        ]
    }
    fields = ",".join([
        "case_id",
        "demographic.days_to_death",
        "demographic.vital_status",
        "diagnoses.days_to_last_follow_up",
        "diagnoses.new_tumor_event_after_initial_treatment",
        "diagnoses.days_to_new_tumor_event_after_initial_treatment",
        "project.project_id",
    ])
    params = {
        "filters": json.dumps(filters),
        "fields": fields,
        "size": "2000",
        "format": "JSON",
    }

    try:
        resp = httpx.get(gdc_url, params=params, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        cases = data.get("data", {}).get("hits", [])

        if not cases:
            return {
                "tool": "download_tcga_survival",
                "cohort": cohort,
                "error": f"No clinical data found for TCGA-{cohort}. Verify the cohort abbreviation.",
            }

        survival_data = []
        for case in cases:
            demographics = case.get("demographic", {}) or {}
            diagnoses = (case.get("diagnoses") or [{}])
            diag = diagnoses[0] if diagnoses else {}

            if survival_type == "overall":
                vital_status = demographics.get("vital_status", "").lower()
                days_to_death = demographics.get("days_to_death")
                days_to_last_follow_up = diag.get("days_to_last_follow_up")

                # Determine time and event
                if vital_status == "dead" and days_to_death is not None:
                    time_value = float(days_to_death)
                    event = 1
                elif days_to_last_follow_up is not None:
                    time_value = float(days_to_last_follow_up)
                    event = 0
                else:
                    continue

                survival_data.append({
                    "time_days": time_value,
                    "event": event,
                    "vital_status": vital_status,
                })

            elif survival_type == "disease_free":
                new_tumor = diag.get("new_tumor_event_after_initial_treatment", "")
                days_to_new_tumor = diag.get("days_to_new_tumor_event_after_initial_treatment")
                days_to_last_follow_up = diag.get("days_to_last_follow_up")

                if new_tumor and new_tumor.lower() in ("yes", "true"):
                    if days_to_new_tumor is not None:
                        time_value = float(days_to_new_tumor)
                        event = 1
                    else:
                        continue
                elif days_to_last_follow_up is not None:
                    time_value = float(days_to_last_follow_up)
                    event = 0
                else:
                    continue

                survival_data.append({
                    "time_days": time_value,
                    "event": event,
                    "new_tumor_event": new_tumor,
                })

        if not survival_data:
            return {
                "tool": "download_tcga_survival",
                "cohort": cohort,
                "survival_type": survival_type,
                "error": f"No usable survival data found for TCGA-{cohort} ({survival_type}).",
            }

        # Compute Kaplan-Meier curve
        times = [d["time_days"] for d in survival_data]
        events = [d["event"] for d in survival_data]

        # Sort by time
        sorted_pairs = sorted(zip(times, events))
        times = [p[0] for p in sorted_pairs]
        events = [p[1] for p in sorted_pairs]

        # KM estimator
        survival_prob = [1.0]
        time_points = [0]
        n_at_risk = len(times)
        current_survival = 1.0
        censor_times = []

        i = 0
        while i < len(times):
            t = times[i]
            # Gather all events at this time
            deaths = 0
            j = i
            while j < len(times) and times[j] == t:
                if events[j] == 1:
                    deaths += 1
                else:
                    censor_times.append(t)
                j += 1
            n_at_risk_now = n_at_risk
            if deaths > 0 and n_at_risk_now > 0:
                current_survival *= (1 - deaths / n_at_risk_now)
            time_points.append(t)
            survival_prob.append(current_survival)
            n_at_risk -= (j - i)
            i = j

        # Build Plotly HTML
        surv_type_label = "Overall Survival" if survival_type == "overall" else "Disease-Free Survival"
        n_events = sum(1 for e in events if e == 1)
        n_censored = sum(1 for e in events if e == 0)
        median_surv = None
        for k in range(len(survival_prob)):
            if survival_prob[k] <= 0.5:
                median_surv = time_points[k]
                break

        title_text = f"TCGA-{cohort} {surv_type_label} (n={len(survival_data)}, events={n_events}, censored={n_censored})"
        if median_surv:
            title_text += f"<br>Median survival: {median_surv:.0f} days"

        # Convert to years for readability
        time_years = [t / 365.25 for t in time_points]
        max_x = max(time_years) if time_years else 1

        html = f"""<!DOCTYPE html>
<html><head>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>body{{margin:0;padding:0;background:#fff;}} .plotly .modebar{{display:none!important;}}</style>
</head><body>
<div id="plot" style="width:100%;height:420px;"></div>
<script>
Plotly.newPlot('plot', [{{
    x: {time_years},
    y: {survival_prob},
    mode: 'lines',
    name: '{surv_type_label}',
    line: {{color: '#092426', width: 2.5}},
    hovertemplate: 'Time: %{{x:.1f}} yr<br>Survival: %{{y:.3f}}<extra></extra>'
}}], {{
    title: {{text: `{title_text}`, font: {{family: 'Inter, sans-serif', size: 14, color: '#092426'}}}},
    xaxis: {{title: 'Time (years)', gridcolor: '#eee', zerolinecolor: '#ccc', tickfont: {{family: 'Inter'}}, dtick: 1, range: [0, Math.min({max_x:.1f}+0.5, 15)]}},
    yaxis: {{title: 'Survival Probability', gridcolor: '#eee', zerolinecolor: '#ccc', tickfont: {{family: 'Inter'}}, range: [0, 1.05]}},
    font: {{family: 'Inter, sans-serif', color: '#333'}},
    plot_bgcolor: '#fff',
    paper_bgcolor: '#fff',
    margin: {{l: 60, r: 20, t: 60, b: 50}},
    showlegend: true,
    legend: {{x: 0.7, y: 0.95, font: {{size: 11}}}},
    hovermode: 'x',
}}, {{responsive: true, displayModeBar: false}});
</script>
</body></html>"""

        return {
            "tool": "download_tcga_survival",
            "cohort": cohort,
            "survival_type": survival_type,
            "num_patients": len(survival_data),
            "n_events": n_events,
            "n_censored": n_censored,
            "median_survival_days": median_surv,
            "data": survival_data,
            "status": "success",
            "visualization": {
                "type": "plotly",
                "title": f"TCGA-{cohort} {surv_type_label}",
                "html": html,
            }
        }

    except Exception as e:
        return {
            "tool": "download_tcga_survival",
            "cohort": cohort,
            "error": f"Failed to fetch TCGA data: {e}",
        }


@register_tool("run_python_plot")
def run_python_plot(code: str, title: str = "", pretty: bool = True) -> dict:
    """Execute plotting code and return image."""
    import builtins
    import os as _os
    import io as _io
    import base64 as _base64
    import traceback as _traceback
    from pathlib import Path as _Path

    WORKSPACE = _Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import numpy as np
        import pandas as pd
    except ImportError as e:
        return {"tool": "run_python_plot", "result": f"Missing plotting library: {e}"}

    if pretty:
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except Exception:
            pass
        sns.set_context("notebook", font_scale=1.2)
        sns.set_style("whitegrid")
        plt.rcParams.update({
            'figure.figsize': (10, 6),
            'figure.titlesize': 18,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 11,
            'figure.facecolor': '#f8f9fa',
        })

    exec_globals = {
        "__builtins__": builtins,
        "__name__": "__main__",
        "os": _safe_os, "sys": sys, "json": json, "subprocess": subprocess,
        "tempfile": tempfile, "base64": _base64, "io": _io, "textwrap": textwrap,
        "Path": _Path, "httpx": httpx, "np": np, "pd": pd,
        "plt": plt, "sns": sns, "np": np, "pd": pd,
        "matplotlib": matplotlib,
        "WORKSPACE": WORKSPACE,
    }

    try:
        # Record PNG files in WORKSPACE before exec to detect newly-saved ones
        _png_before = set(WORKSPACE.rglob("*.png")) if WORKSPACE.exists() else set()

        plt.close('all')  # Clear any previous figures
        exec(compile(code, "<run_python_plot>", "exec"), exec_globals)

        # Strategy 1: try to capture the most recent matplotlib figure
        fig = plt.gcf()
        b64_data = ""
        if fig.axes:
            buf = _io.BytesIO()
            fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor=fig.get_facecolor())
            b64_data = _base64.b64encode(buf.getvalue()).decode()

        plt.close('all')

        # Strategy 2: if no in-memory figure, look for PNG files the agent
        # code saved to WORKSPACE (agent code often calls plt.savefig()
        # followed by plt.close(), which makes plt.gcf() return an empty fig)
        if not b64_data:
            _png_after = set(WORKSPACE.rglob("*.png")) if WORKSPACE.exists() else set()
            _new_pngs = sorted(_png_after - _png_before, key=lambda p: p.stat().st_mtime, reverse=True)
            if _new_pngs:
                # Read the most recently created PNG
                with open(_new_pngs[0], 'rb') as _f:
                    b64_data = _base64.b64encode(_f.read()).decode()

        if not b64_data:
            return {"tool": "run_python_plot", "result": "No image generated. Ensure you're creating a plot with plt or sns."}

        return {
            "tool": "run_python_plot",
            "visualization": {
                "type": "image",
                "image": "data:image/png;base64," + b64_data,
                "title": title,
            },
        }
    except Exception as e:
        plt.close('all')
        tb_str = _traceback.format_exc()
        return {"tool": "run_python_plot", "result": f"Error: {tb_str[-1000:]}"}


@register_tool("plotly_plot")
def plotly_plot(code: str, title: str = "Plot") -> dict:
    """Execute Plotly code and return interactive HTML visualization."""
    import builtins
    import io as _io
    import traceback as _traceback
    from pathlib import Path as _Path

    WORKSPACE = _Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))

    try:
        import plotly.express as px
        import plotly.graph_objects as go
        import numpy as np
        import pandas as pd
    except ImportError as e:
        return {"tool": "plotly_plot", "result": f"Missing plotly library: {e}"}

    exec_globals = {
        "__builtins__": builtins,
        "__name__": "__main__",
        "os": _safe_os, "sys": sys, "json": json, "subprocess": subprocess,
        "tempfile": tempfile, "Path": _Path, "httpx": httpx,
        "np": np, "pd": pd, "px": px, "go": go,
        "WORKSPACE": WORKSPACE,
    }

    try:
        exec(compile(code, "<plotly_plot>", "exec"), exec_globals)

        fig = exec_globals.get("fig")
        if fig is None:
            return {"tool": "plotly_plot", "result": "No figure named 'fig' was created. Use `fig = px.(...)` or `fig = go.Figure(...)`. "}

        html_data = fig.to_html(include_plotlyjs='cdn', config={'responsive': True})
        if not html_data:
            return {"tool": "plotly_plot", "result": "No HTML generated. Ensure you create a figure named 'fig'."}

        return {
            "tool": "plotly_plot",
            "visualization": {
                "type": "plotly",
                "html": html_data,
                "title": title,
            },
        }
    except Exception as e:
        tb_str = _traceback.format_exc()
        return {"tool": "plotly_plot", "result": f"Error: {tb_str[-1000:]}"}


# =============================================================================
# Modal serverless tools
# =============================================================================

from modal_tasks import (
    MODAL_AVAILABLE,
    BIO_TASKS,
    run_modal_task,
    create_modal_task,
    get_available_tasks,
)


@register_tool("run_modal_job")
def run_modal_job(job_type: str, params: dict) -> dict:
    """Execute a pre-defined bioinformatics task on Modal's serverless cloud.

    Args:
        job_type: One of 'star_alignment', 'download_sra', 'deseq2'
        params: Job-specific parameters dict
    """
    if not MODAL_AVAILABLE:
        return {
            "tool": "run_modal_job",
            "error": "Modal SDK not installed. Install with: pip install modal && modal setup",
            "available_locally": list(BIO_TASKS.keys()) if MODAL_AVAILABLE else [],
        }

    # Validate job_type
    valid_types = list(BIO_TASKS.keys()) + list(get_available_tasks())
    # Also include dynamically created tasks
    from modal_tasks import _dynamic_modal_tasks
    valid_types = list(BIO_TASKS.keys()) + list(_dynamic_modal_tasks.keys())

    if job_type not in BIO_TASKS and job_type not in _dynamic_modal_tasks:
        return {
            "tool": "run_modal_job",
            "error": f"Unknown job_type: '{job_type}'. Available: {valid_types}",
        }

    # Validate params against the task's schema
    task = BIO_TASKS.get(job_type) or _dynamic_modal_tasks.get(job_type)
    task_params = task.get("parameters", task.get("params_schema", {}))
    required_params = task_params.get("required", [])

    missing = [p for p in required_params if p not in params]
    if missing:
        return {
            "tool": "run_modal_job",
            "error": f"Missing required parameters for '{job_type}': {missing}",
            "required": required_params,
        }

    result = run_modal_task(job_type, params)
    result["tool"] = "run_modal_job"
    result["job_type"] = job_type
    return result


@register_tool("create_modal_tool")
def create_modal_tool_handler(
    name: str,
    description: str,
    parameters: dict,
    code: str,
    cpu: float = 2.0,
    memory_mb: int = 4096,
    gpu: str | None = None,
    timeout: int = 3600,
    image_packages: list | None = None,
    image_apt_packages: list | None = None,
) -> dict:
    """Create a new Modal serverless task dynamically.

    The created task becomes available as a run_modal_job job_type.
    """
    if not MODAL_AVAILABLE:
        return {
            "tool": "create_modal_tool",
            "error": "Modal SDK not installed. Install with: pip install modal && modal setup",
        }

    result = create_modal_task(
        name=name,
        description=description,
        parameters=parameters,
        code=code,
        cpu=cpu,
        memory_mb=memory_mb,
        gpu=gpu,
        timeout=timeout,
        image_packages=image_packages,
        image_apt_packages=image_apt_packages,
    )

    # If created successfully, also register as a run_modal_job-compatible entry
    if result.get("status") == "created":
        safe_name = result["task"]
        # Register the tool definition for the agent so it knows this job_type exists
        new_task = _dynamic_modal_tasks.get(safe_name)
        if new_task:
            # Add a run_modal_job-style entry that the agent can discover
            result["available_jobs"] = get_available_tasks()

    result["tool"] = "create_modal_tool"
    return result


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name with the given arguments."""
    if name not in TOOL_IMPLS:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = TOOL_IMPLS[name](**args)
        if result is None:
            return json.dumps({"error": f"Tool {name} returned no result"})
        return json.dumps(result, default=str)
    except TypeError as e:
        if "unexpected keyword argument" in str(e):
            return json.dumps({"error": f"Tool {name} received unexpected argument: {e}"})
        return json.dumps({"error": f"Tool {name} type error: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Tool {name} failed: {type(e).__name__}: {e}"})


# =============================================================================
# Dynamic tool creation
# =============================================================================

from dynamic_tools import create_tool as _create_tool_impl
from dynamic_tools import load_dynamic_tools as _load_dynamic_tools


@register_tool("create_tool")
def create_tool_handler(name: str, description: str, parameters: dict, code: str) -> dict:
    """Create a new dynamic tool and register it."""
    return _create_tool_impl(
        name=name,
        description=description,
        parameters=parameters,
        code=code,
    )


@register_tool("execute_python")
def execute_python(code: str, description: str = "") -> dict:
    """Execute arbitrary Python code and return stdout/stderr."""
    import sys as _sys
    from pathlib import Path as _Path

    WORKSPACE = _Path(os.environ.get("ESAPIENS_DATA_DIR", os.path.expanduser("~/esapiens-data")))

    # Imports available to executed code
    import builtins
    import os as _os
    import json as _json
    import subprocess as _subprocess
    import tempfile as _tempfile
    import base64 as _base64
    import io as _io
    import textwrap as _textwrap
    from pathlib import Path as _Path

    try:
        import httpx as _httpx
    except ImportError:
        _httpx = None

    try:
        import numpy as _np
        import pandas as _pd
    except ImportError:
        _np = None
        _pd = None

    exec_globals = {
        "__builtins__": builtins,
        "__name__": "__main__",
        "os": _safe_os,
        "sys": _sys,
        "json": _json,
        "subprocess": _subprocess,
        "tempfile": _tempfile,
        "base64": _base64,
        "io": _io,
        "textwrap": _textwrap,
        "Path": _Path,
        "httpx": _httpx,
        "np": _np,
        "pd": _pd,
        "WORKSPACE": WORKSPACE,
    }

    old_stdout = _sys.stdout
    old_stderr = _sys.stderr
    _sys.stdout = _io.StringIO()
    _sys.stderr = _io.StringIO()

    try:
        compiled = compile(code, "<exec>", "exec")
        exec(compiled, exec_globals)
        stdout_val = _sys.stdout.getvalue()
        stderr_val = _sys.stderr.getvalue()
        _sys.stdout = old_stdout
        _sys.stderr = old_stderr
        return {
            "tool": "execute_python",
            "description": description,
            "exit_code": 0,
            "stdout": stdout_val[-4000:] if len(stdout_val) > 4000 else stdout_val,
            "result": stdout_val[-2000:] if len(stdout_val) > 2000 else stdout_val,
        }
    except Exception as e:
        import traceback
        stderr_val = _sys.stderr.getvalue()
        stdout_val = _sys.stdout.getvalue()
        _sys.stdout = old_stdout
        _sys.stderr = old_stderr
        tb_str = traceback.format_exc()
        return {
            "tool": "execute_python",
            "description": description,
            "exit_code": 1,
            "stdout": stdout_val[-2000:] if len(stdout_val) > 2000 else stdout_val,
            "stderr": stderr_val[-2000:] if len(stderr_val) > 2000 else stderr_val,
            "result": f"Error: {e}\n{tb_str[-1000:]}",
        }


# Load dynamic tools on module import
try:
    _loaded = _load_dynamic_tools()
    if _loaded:
        print(f"[tools] Loaded {len(_loaded)} dynamic tools: {[t['name'] for t in _loaded]}")
except Exception as e:
    print(f"[tools] Warning: Failed to load dynamic tools: {e}")
