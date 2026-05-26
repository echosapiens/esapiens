# E.sapiens Agent — Environment Self-Description

## THIS IS YOUR ENVIRONMENT. Read carefully. You have full awareness of it.

---

## File System Layout

```
/app                          ← backend root (inside Docker container)
  agent.py                    ← LangGraph ReAct loop + 4-node graph
  tools.py                    ← Tool definitions + execute_python guard
  skill_loader.py             ← bioSkills loader (SKILL.md → LLM context)
  intent_classifier.py        ← Keyword → skill path mapper (INTENT_KEYWORDS dict)
  prompts.py / prompts.json   ← All LLM system prompts (13 prompts, 5 tiers)
  modal_tasks.py              ← Modal.com task definitions
  dynamic_tools.py            ← User-defined tool creation
  main.py                     ← FastAPI app entry point
  data/                       ← Per-user workspace storage
    workspaces/
      usr_<hashid>/
        sessions/<session_id>/
  bioSkills/                  ← bio skills (SKILL.md files; see below)

/root/persistent              ← Named volume mount for persistent data

On Mac (local dev):
  ~/.../Esapiens-Sprint-2/      ← git repo root; contains docker-compose.yml
  ~/.../Esapiens-Sprint-2/bioSkills/   ← skills source (copied into Docker image)
```

## Docker / Deployment

- Build context: repo root (Esapiens-Sprint-2/), NOT backend/
- Dockerfile: backend/Dockerfile — copies backend/ and bioSkills/ into /app/
- docker-compose: builds from backend/Dockerfile with context .
- Skill path in container: /app/bioSkills/ (NOT nested under backend/)
- bioSkills are COPIED into the Docker image at build time. They are NOT dynamic.

## How Skills Work

**Skill path format** (used everywhere internally):
```
category/sub-category   e.g., structural-biology/structure-io
```

The intent classifier (intent_classifier.py, INTENT_KEYWORDS dict) matches your query to a skill path. Keywords are case-insensitive. If query mentions "pdb", "structure", "atom", "residue" —> structural-biology/structure-io. If query contains a PDB-like 4-char ID (e.g., 1ABC) as fallback —> structural-biology/structure-io.

**Skill loader** (skill_loader.py):
```python
base_path = Path(__file__).parent.parent / "bioSkills"
# In container: /app/bioSkills
skill_file = base_path / skill_path / "SKILL.md"
# e.g., /app/bioSkills/structural-biology/structure-io/SKILL.md
```
If the file exists -> content loaded. If NOT -> "Skill not found: {path}" printed.

**All available skills**:
structural-biology/structure-io
structural-biology/geometric-analysis
structural-biology/alphafold-predictions
sequence-io, sequence-manipulation, alignment
variant-calling, variant-calling/vcf-basics, variant-calling/variant-annotation, variant-calling/clinical-interpretation
rna-quantification, differential-expression
read-alignment, read-qc, methylation-analysis
chip-seq, atac-seq
phylogenetics, population-genetics
metagenomics, microbiome
proteomics, pathway-analysis
database-access, database-access/interaction-databases
single-cell, crispr-screens, machine-learning
clinical-biostatistics, ui_ux, data-visualization
primer-design, chemoinformatics

## Tool Categories

execute_python — sandboxed exec() on VPS. Lightweight tasks ONLY (data reshaping, file I/O, simple stats). NEVER use for bio compute (STAR, DESeq2, TCGA survival, scanpy, etc.) — the guard rejects it.
run_python_plot — matplotlib/seaborn static figures on VPS.
plotly_plot — Plotly interactive charts on VPS.
download_pdb — RCSB PDB fetch.
parse_structure — Biopython MMCIF/PDB parser.
search_literature — PubMed/Brave Search.
download_tcga_survival — TCGA Xena Hub public clinical data.
create_tool — Dynamic tool definition builder.
run_bio_pipeline — Dispatch heavy pipeline to Modal BioContainer.
run_modal_job — Generic BioContainer dispatch on Modal.com.
create_modal_tool — Register a new Modal.compute task type.
find_biocontainer — Quay.io biocontainer registry lookup.
run_custom_script — Arbitrary code on Modal GPU node.
get_job_status — Poll a Modal job.
list_available_tools — Enumerate all tool definitions.

## execute_python — Bio Guard

The guard REJECTS and redirects to Modal if your code contains:
- Bio tool commands: STAR, fasterq-dump, samtools, bwa, DESeq2, etc.
- Heavy Python: import scanpy, import anndata, import pysam, import pybedtools
- TCGA/GEO patterns: tcga-xena-hub.s3, gdc.cancer.gov, PAM50, survival analysis, OS_TIME, OS_EVENT
- Shell injection: os.system, os.popen
- Large FTP downloads from NCBI

HEAVY BIO COMPUTATION -> use run_bio_pipeline or run_modal_job. NEVER on VPS.

## 4-node Graph Architecture

classify_intent -> call_model -> tools_node -> critic_node -> call_model (loop) -> finalize

Working memory (debug_log) tracks all tool call history. After 3 consecutive failures of the same strategy, critic_node injects a [STRATEGY SWITCH] directive.

## Environment Variables

OPENROUTER_API_KEY, MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, JWT_SECRET, ESAPIENS_DATA_DIR=/root/persistent, CORS_ORIGINS, OPENROUTER_MODEL.

## Key Paths in execute_python

/tmp/ — ephemeral (survives exec() call, cleared on container restart)
/root/persistent/ — named volume, survives restart
Modal /modal_workdir/ — container workdir on Modal, use absolute paths.

## Skill Loading Flow

User query -> intent_classifier.py:classify_query() -> INTENT_KEYWORDS match -> list of skill paths -> skill_loader.py:load_skills(skill_paths) -> looks for /app/bioSkills/{skill_path}/SKILL.md -> content injected into system prompt as skill_context_block.
If the skill path directory does not exist inside the Docker image -> "Skill not found" error. This is a Docker build issue — the bioSkills directory was not copied into the image.
