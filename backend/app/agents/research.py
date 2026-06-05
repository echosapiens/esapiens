"""Phase 1: Research & Discovery Agent.

The LLM is constrained to a pure classification task — it only determines
which bioinformatics tool the user is asking for. After classification, a
web-search-powered step fetches real documentation and uses an LLM to
generate a working bash command line, replacing the old hardcoded commands.
"""

import logging
from typing import Optional
from app.openrouter import OpenRouterClient
from app.biocontainers import resolve_tool_image
from app.tool_search import search_tool_docs

logger = logging.getLogger(__name__)

# All known tools with their resolved properties.
# The 'command' field has been removed — commands are now generated
# dynamically by the LLM using real documentation from web search.
TOOL_REGISTRY = {
    "mafft": {
        "name": "mafft",
        "description": "Multiple sequence alignment using MAFFT",
        "image": "quay.io/biocontainers/mafft:7.313--0",
        "inputs": [{"file_type": "fasta", "mount_path": "/data/input/", "description": "Input FASTA sequences to align"}],
        "outputs": [{"file_type": "aln", "mount_path": "/data/output/", "description": "Multiple sequence alignment output"}],
    },
    "samtools": {
        "name": "samtools",
        "description": "Tools for SAM/BAM file manipulation and statistics",
        "image": "quay.io/biocontainers/samtools:1.23.1--ha83d96e_0",
        "inputs": [{"file_type": "bam", "mount_path": "/data/input/", "description": "Input BAM alignment file"}],
        "outputs": [{"file_type": "bam", "mount_path": "/data/output/", "description": "Processed BAM file"},
                    {"file_type": "txt", "mount_path": "/data/output/", "description": "Alignment statistics"}],
    },
    "star": {
        "name": "star",
        "description": "Spliced Transcripts Alignment to a Reference (RNA-seq aligner)",
        "image": "quay.io/biocontainers/star:2.7.11b--h5ca1c30_8",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "RNA-seq FASTQ read files"}],
        "outputs": [{"file_type": "bam", "mount_path": "/data/output/", "description": "Aligned and sorted BAM file"}],
    },
    "bwa": {
        "name": "bwa",
        "description": "Burrows-Wheeler Aligner for short-read alignment",
        "image": "quay.io/biocontainers/bwa:0.7.19--h577a1d6_1",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "FASTQ read files"}],
        "outputs": [{"file_type": "sam", "mount_path": "/data/output/", "description": "Alignment SAM file"}],
    },
    "fastqc": {
        "name": "fastqc",
        "description": "Quality control for high-throughput sequencing data",
        "image": "quay.io/biocontainers/fastqc:0.11.3--0",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "Input FASTQ files for QC"}],
        "outputs": [{"file_type": "html", "mount_path": "/data/output/", "description": "QC report"}],
    },
    "blast": {
        "name": "blast",
        "description": "Basic Local Alignment Search Tool for sequence similarity",
        "image": "quay.io/biocontainers/blast:2.17.0--h66d330f_0",
        "inputs": [{"file_type": "fasta", "mount_path": "/data/input/", "description": "Query FASTA file"}],
        "outputs": [{"file_type": "txt", "mount_path": "/data/output/", "description": "BLAST results"}],
    },
    "bowtie2": {
        "name": "bowtie2",
        "description": "Fast and sensitive short-read alignment",
        "image": "quay.io/biocontainers/bowtie2:2.5.5--ha27dd3b_0",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "FASTQ read files"}],
        "outputs": [{"file_type": "sam", "mount_path": "/data/output/", "description": "Alignment SAM file"}],
    },
    "trimmomatic": {
        "name": "trimmomatic",
        "description": "Flexible read trimming and adapter removal",
        "image": "quay.io/biocontainers/trimmomatic:0.40--hdfd78af_0",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "Raw FASTQ files"}],
        "outputs": [{"file_type": "fastq.gz", "mount_path": "/data/output/", "description": "Trimmed FASTQ files"}],
    },
    "clustalo": {
        "name": "clustalo",
        "description": "Clustal Omega for multiple sequence alignment",
        "image": "quay.io/biocontainers/clustalo:1.2.4--h503566f_10",
        "inputs": [{"file_type": "fasta", "mount_path": "/data/input/", "description": "Input FASTA sequences"}],
        "outputs": [{"file_type": "aln", "mount_path": "/data/output/", "description": "Multiple sequence alignment"}],
    },
    "muscle": {
        "name": "muscle",
        "description": "MUSCLE multiple sequence alignment",
        "image": "quay.io/biocontainers/muscle:5.3--h9948957_3",
        "inputs": [{"file_type": "fasta", "mount_path": "/data/input/", "description": "Input FASTA sequences"}],
        "outputs": [{"file_type": "aln", "mount_path": "/data/output/", "description": "Multiple sequence alignment"}],
    },
    "hisat2": {
        "name": "hisat2",
        "description": "Hierarchical indexing for spliced alignment of transcripts",
        "image": "quay.io/biocontainers/hisat2:2.2.2--h503566f_0",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "RNA-seq FASTQ read files"}],
        "outputs": [{"file_type": "sam", "mount_path": "/data/output/", "description": "Aligned SAM file"}],
    },
    "salmon": {
        "name": "salmon",
        "description": "Transcript quantification from RNA-seq reads",
        "image": "quay.io/biocontainers/salmon:1.11.4--h7f96273_0",
        "inputs": [{"file_type": "fastq.gz", "mount_path": "/data/input/", "description": "RNA-seq FASTQ read files"}],
        "outputs": [{"file_type": "sf", "mount_path": "/data/output/", "description": "Salmon quantification (quant.sf)"}],
    },
}


class ResearchAgent:
    """Analyzes user requests to identify the correct bioinformatics tool,
    then fetches real docs and generates a working command line via LLM.

    The LLM is used as a pure classifier — it selects from a fixed list of
    known tools. After classification, tool_search fetches documentation,
    and a second LLM call generates the actual bash command using those docs.
    """

    # Keyword-to-tool mapping for zero-LLM fallback
    KEYWORD_MAP = {
        "mafft": ["mafft", "multiple sequence alignment", "msa", "align sequences"],
        "samtools": ["samtools", "bam", "alignment statistics", "flagstat", "sort bam", "index bam"],
        "star": ["star", "rna", "rna-seq", "rna seq", "rna sequencing", "spliced alignment", "transcript alignment", "spliced transcript", "download", "align reads"],
        "bwa": ["bwa", "burrows", "short read alignment", "mem"],
        "fastqc": ["fastqc", "quality control", "qc report", "read quality"],
        "blast": ["blast", "nucleotide blast", "blastn", "blastp", "sequence similarity"],
        "bowtie2": ["bowtie", "bowtie2"],
        "trimmomatic": ["trim", "trimmomatic", "adapter removal", "read trimming"],
        "clustalo": ["clustal", "clustalo", "clustal omega"],
        "muscle": ["muscle"],
        "hisat2": ["hisat2", "hisat"],
        "salmon": ["salmon", "quantify", "quantification", "transcript quantification"],
    }

    def __init__(self, openrouter: OpenRouterClient):
        self.client = openrouter

    def process(self, user_prompt: str) -> dict:
        """
        Classifies the user's prompt into a tool name, fetches real docs
        via web search, and generates a working command line via LLM.

        Returns dict with keys: tool_name, tool_description, suggested_image,
        required_inputs, expected_outputs, pipeline_steps, search_findings
        """
        # --- Step 1: Classify which tool the user needs (existing logic) ---
        tool_name = self._classify_tool_llm(user_prompt)

        # Fallback to keyword matching if LLM failed
        if not tool_name or tool_name == "unknown":
            tool_name = self._classify_tool_keywords(user_prompt)

        # Look up tool metadata in registry
        tool = TOOL_REGISTRY.get(tool_name.lower())

        if not tool:
            return {
                "tool_name": "unknown",
                "tool_description": f"Unable to identify tool from: {user_prompt}",
                "suggested_image": "",
                "required_inputs": [],
                "expected_outputs": [],
                "pipeline_steps": [],
                "generated_command": "",
                "search_findings": None,
            }

        # --- Step 2: Web search for real documentation ---
        search_result = search_tool_docs(tool_name, user_prompt)
        search_docs = search_result.get("usage_summary", "")
        search_sources = [f["url"] for f in search_result.get("findings", [])]
        search_summary = search_result.get("usage_summary", "")[:200]
        search_error = search_result.get("error")

        if search_error:
            logger.warning("Tool search failed for %s: %s", tool_name, search_error)

        # --- Step 3: Generate command line via LLM using real docs ---
        generated_command = self._generate_command_llm(
            tool_name=tool["name"],
            tool_description=tool["description"],
            user_prompt=user_prompt,
            search_docs=search_docs,
        )

        # If LLM command generation fails, fall back to a generic placeholder
        if not generated_command:
            generated_command = f"# Could not auto-generate command for {tool_name}; please provide manually"
            logger.warning("LLM command generation failed for tool %s", tool_name)

        # Build the search_findings dict for streaming as 'thought' events
        search_findings = {
            "tool_name": tool_name,
            "search_summary": search_summary,
            "sources": search_sources,
            "docs_snippet": search_docs[:2000] if search_docs else "",  # truncate for streaming
            "docs_length": len(search_docs),
            "search_error": search_error,
            "generated_command": generated_command,
        }

        return {
            "tool_name": tool["name"],
            "tool_description": tool["description"],
            "suggested_image": tool["image"],
            "required_inputs": tool["inputs"],
            "expected_outputs": tool["outputs"],
            "pipeline_steps": [generated_command],
            "generated_command": generated_command,
            "search_findings": search_findings,
        }

    def _generate_command_llm(
        self,
        tool_name: str,
        tool_description: str,
        user_prompt: str,
        search_docs: str,
    ) -> str:
        """
        Uses the LLM to generate a working bash command line for the
        identified tool, informed by real documentation from web search.

        Returns the generated command string, or empty string on failure.
        """
        if not self.client or not self.client.api_key:
            return ""

        docs_section = ""
        if search_docs:
            docs_section = (
                f"\n\n--- REAL DOCUMENTATION for {tool_name} ---\n"
                f"{search_docs}\n"
                f"--- END DOCUMENTATION ---\n"
            )

        system_prompt = (
            "You are an expert bioinformatics command-line engineer. "
            "Your ONLY job is to output a single, working bash command line "
            "that runs the specified bioinformatics tool inside a BioContainer.\n\n"
            "STRICT RULES:\n"
            "- Output ONLY the bash command. No JSON, no markdown, no explanation, no backticks.\n"
            "- Use ACTUAL tool syntax from the provided documentation — do NOT guess or invent flags.\n"
            "- ALL input file paths MUST be under /data/input/ (e.g. /data/input/reads.fastq).\n"
            "- ALL output file paths MUST be under /data/output/ (e.g. /data/output/alignment.sam).\n"
            "- The container starts EMPTY — no data files exist. You MUST download input data first.\n"
            "  Use this exact syntax for downloads (the download runs in Ubuntu which has python3):\n"
            "  python3 -c \"import urllib.request; urllib.request.urlretrieve('URL', '/data/input/filename')\"\n"
            "  Chain all downloads with && before the main tool command.\n"
            "- For small FASTA sequences, use printf to write them inline:\n"
            "  printf '>seq1\\\\nACGTACGT\\\\n>seq2\\\\nTGCATGCA\\\\n' > /data/input/sequences.fasta\n"
            "- Download real test data from these VERIFIED URLs:\n"
            "  * Protein FASTA: https://rest.uniprot.org/uniprotkb/P62988.fasta (RBL_HUMAN)\n"
            "  * Protein FASTA: https://rest.uniprot.org/uniprotkb/P31946.fasta (14-3-3 protein)\n"
            "  * Nucleotide FASTA: https://www.ebi.ac.uk/ena/browser/api/fasta/AY445571.1\n"
            "  * Nucleotide FASTA: https://www.ebi.ac.uk/ena/browser/api/fasta/X17216.1\n"
            "- If the tool requires an index/database (makeblastdb, bwa index, bowtie2-build, "
            "hisat2-build, salmon index, STAR --runMode genomeGenerate), build it BEFORE the main "
            "command using &&. The index output must live under /data/input/.\n"
            "- For multi-step workflows, chain ALL steps with &&.\n"
            "- Do NOT include any sudo, apt-get, conda, or pip install commands.\n"
            "- Do NOT include any comments or echo statements.\n"
            "- The tool command will run inside a BioContainer that has the tool installed.\n"
            "- Do NOT define shell functions. Only use simple commands chained with &&.\n"
        )

        user_message = (
            f"Tool: {tool_name}\n"
            f"Description: {tool_description}\n"
            f"User request: {user_prompt}"
            f"{docs_section}\n"
            "Generate the bash command line now. Output ONLY the command."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            result = self.client.chat_completion(messages, temperature=0.0)

            if "error" in result:
                logger.error("LLM command generation error: %s", result["error"])
                return ""

            content = result.get("content", "").strip()

            # Strip markdown code fences if the model wrapped the command
            if content.startswith("```"):
                lines = content.split("\n")
                # Remove first and last lines (code fences)
                lines = [l for l in lines if not l.strip().startswith("```")]
                content = "\n".join(lines).strip()

            # Remove any trailing/leading whitespace and normalize
            content = content.strip()

            # Validate that the command references the tool name somewhere
            # (basic sanity check)
            if tool_name.lower().split()[0] not in content.lower() and content:
                logger.warning(
                    "Generated command may not reference tool %s: %s",
                    tool_name, content[:200],
                )

            return content

        except Exception as e:
            logger.error("Exception during LLM command generation: %s", e)
            return ""

    def _classify_tool_llm(self, prompt: str) -> str:
        """
        Uses the LLM as a PURE classifier — it only returns a tool name
        from a fixed list. No image tags, no URLs, no pipeline steps.
        Falls back to 'unknown' if LLM is unavailable.
        """
        if not self.client or not self.client.api_key:
            return "unknown"
        tool_list = ", ".join(sorted(TOOL_REGISTRY.keys()))
        system_prompt = (
            "You are a tool classifier. Given a user's bioinformatics request, "
            "respond with ONLY the single best tool name from this list:\n"
            f"{tool_list}\n\n"
            "Rules:\n"
            "- If the request involves alignment, choose the primary aligner\n"
            "- If the request involves quantification, choose the quantifier\n"
            "- Return ONLY the tool name, no JSON, no explanation, no punctuation\n"
            "- If no tool matches, return 'unknown'"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        result = self.client.chat_completion(messages, temperature=0.0)
        if "error" in result:
            return "unknown"

        content = result.get("content", "").strip().lower()
        # Validate the response is actually a known tool
        if content in TOOL_REGISTRY:
            return content
        return "unknown"

    def _classify_tool_keywords(self, prompt: str) -> str:
        """
        Score-based keyword tool classification.
        Returns the tool with the most specific keyword hits.
        Explicit tool names (star, salmon, mafft) get a 2x bonus.
        General terms (align, sam, fastq) are deprioritized.
        """
        prompt_lower = prompt.lower()
        scores: dict[str, float] = {}

        for tool, keywords in self.KEYWORD_MAP.items():
            for kw in keywords:
                if kw in prompt_lower:
                    # Explicit tool name = 2x weight
                    weight = 2.0 if kw == tool else 1.0
                    scores[tool] = scores.get(tool, 0) + weight

        if not scores:
            return "unknown"

        # Return the tool with the highest score
        return max(scores, key=scores.get)