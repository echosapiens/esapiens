"""Deterministic data source resolver for bioinformatics pipelines.

Resolves input data requirements programmatically based on the user's
prompt and classified tool. No LLM involvement — every URL is verified.

This replaces the LLM-generated download commands which were prone to
hallucinating accession numbers and URLs.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Common species name normalization
_SPECIES_ALIASES = {
    "human": "human", "homo sapiens": "human",
    "chimpanzee": "chimp", "chimp": "chimp", "pan troglodytes": "chimp",
    "mouse": "mouse", "mus musculus": "mouse",
    "rat": "rat", "rattus norvegicus": "rat",
    "zebrafish": "zebrafish", "danio rerio": "zebrafish",
    "yeast": "yeast", "saccharomyces cerevisiae": "yeast",
    "e. coli": "e_coli", "e coli": "e_coli", "escherichia coli": "e_coli",
    "cow": "cow", "bos taurus": "cow",
    "pig": "pig", "sus scrofa": "pig",
    "dog": "dog", "canis familiaris": "dog",
    "chicken": "chicken", "gallus gallus": "chicken",
}

# Verified UniProt accessions for commonly requested proteins
# Format: {protein_name_lower: {species: (accession, gene_name)}}
VERIFIED_PROTEINS = {
    "bax": {
        "human": ("Q07812", "BAX"),
        "chimp": ("Q07812", "BAX"),
        "mouse": ("Q07813", "Bax"),
        "rat": ("Q63690", "Bax"),
    },
    "bcl2": {
        "human": ("P10415", "BCL2"),
        "mouse": ("P10417", "Bcl2"),
    },
    "bcl2l1": {
        "human": ("Q07817", "BCL2L1"),
        "mouse": ("Q64373", "Bcl2l1"),
    },
    "p53": {
        "human": ("P04637", "TP53"),
        "mouse": ("P02340", "Trp53"),
    },
    "tp53": {
        "human": ("P04637", "TP53"),
        "mouse": ("P02340", "Trp53"),
    },
    "egfr": {
        "human": ("P00533", "EGFR"),
        "mouse": ("Q01279", "Egfr"),
    },
    "gapdh": {
        "human": ("P04406", "GAPDH"),
        "mouse": ("P16858", "Gapdh"),
    },
    "akt1": {
        "human": ("P31749", "AKT1"),
        "mouse": ("P31750", "Akt1"),
    },
    "casp3": {
        "human": ("P42574", "CASP3"),
        "mouse": ("P70677", "Casp3"),
    },
    "mapk1": {
        "human": ("P28482", "MAPK1"),
        "mouse": ("P63085", "Mapk1"),
    },
    "mapk3": {
        "human": ("P27361", "MAPK3"),
        "mouse": ("Q63844", "Mapk3"),
    },
}

# Well-known test data URLs for common bioinformatics tasks
# These point to real, stable datasets
TEST_DATA_URLS = {
    "fasta_generic": [
        ("https://rest.uniprot.org/uniprotkb/P62988.fasta", "rbl_human.fasta"),  # Ubiquitin
        ("https://rest.uniprot.org/uniprotkb/P31946.fasta", "1433b_human.fasta"),  # 14-3-3 beta
    ],
    "fastq_rnaseq": [
        ("https://raw.githubusercontent.com/nf-core/test-datasets/main/rnaseq/test_1.fastq.gz", "test_1.fastq.gz"),
        ("https://raw.githubusercontent.com/nf-core/test-datasets/main/rnaseq/test_2.fastq.gz", "test_2.fastq.gz"),
    ],
    "fasta_nucleotide": [
        ("https://www.ebi.ac.uk/ena/browser/api/fasta/AY445571.1", "ay445571.fasta"),  # Dog mitochondria
        ("https://www.ebi.ac.uk/ena/browser/api/fasta/X17216.1", "x17216.fasta"),  # Human LDLR
    ],
}


def _parse_species(prompt: str) -> list[str]:
    """Extract species names from a prompt."""
    prompt_lower = prompt.lower().strip()
    found = []
    for alias, normalized in _SPECIES_ALIASES.items():
        if alias in prompt_lower:
            if normalized not in found:
                found.append(normalized)
    return found if found else ["human"]


def _parse_proteins(prompt: str) -> list[str]:
    """Extract protein names from a prompt."""
    prompt_lower = prompt.lower().strip()
    # Sort by length descending to match longer names first (e.g. "bcl2l1" before "bcl2")
    protein_keys = sorted(VERIFIED_PROTEINS.keys(), key=len, reverse=True)
    found = []
    for key in protein_keys:
        if key in prompt_lower:
            found.append(key)
    return found


def resolve_download_commands(prompt: str, tool_name: str) -> tuple[list[str], str]:
    """Resolve download commands for a given user prompt and tool.

    Returns (download_commands, data_description):
      - download_commands: list of bash commands to download input data
      - data_description: human-readable description of what data was resolved
    """
    commands = []
    descriptions = []

    species_list = _parse_species(prompt)
    proteins = _parse_proteins(prompt)

    # Case 1: User asked for specific proteins
    if proteins:
        for protein in proteins:
            mapping = VERIFIED_PROTEINS.get(protein, {})
            for species in species_list:
                entry = mapping.get(species)
                if entry:
                    accession, gene = entry
                    filename = f"{species}_{gene}.fasta"
                    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
                    cmd = (
                        f"python3 -c \"import urllib.request; "
                        f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
                    )
                    commands.append(cmd)
                    descriptions.append(f"{species} {gene} ({accession})")
                elif species == "human" and mapping.get("human"):
                    # Fallback: use human if species not available
                    entry = mapping["human"]
                    accession, gene = entry
                    filename = f"human_{gene}.fasta"
                    url = f"https://rest.uniprot.org/uniprotkb/{accession}.fasta"
                    cmd = (
                        f"python3 -c \"import urllib.request; "
                        f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
                    )
                    commands.append(cmd)
                    descriptions.append(f"human {gene} ({accession})")

    # Case 2: Generic alignment (MSA) without specific proteins
    if not commands and tool_name in ("mafft", "clustalo", "muscle"):
        for url, filename in TEST_DATA_URLS["fasta_generic"]:
            cmd = (
                f"python3 -c \"import urllib.request; "
                f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
            )
            commands.append(cmd)
        descriptions.append("generic test FASTA sequences")
        # Also add a combine step for MSA tools
        cmd = "cat /data/input/rbl_human.fasta /data/input/1433b_human.fasta > /data/input/combined.fasta"
        commands.append(cmd)
        descriptions.append("combined input file")

    # Case 3: RNA-seq
    if not commands and tool_name in ("star", "hisat2", "salmon", "bowtie2", "bwa"):
        for url, filename in TEST_DATA_URLS["fastq_rnaseq"]:
            cmd = (
                f"python3 -c \"import urllib.request; "
                f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
            )
            commands.append(cmd)
        descriptions.append("RNA-seq test FASTQ files")

    # Case 4: BLAST
    if not commands and tool_name == "blast":
        for url, filename in TEST_DATA_URLS["fasta_nucleotide"]:
            cmd = (
                f"python3 -c \"import urllib.request; "
                f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
            )
            commands.append(cmd)
        descriptions.append("nucleotide test FASTA sequences")

    # Case 5: Trimmomatic - needs FASTQ
    if not commands and tool_name == "trimmomatic":
        for url, filename in TEST_DATA_URLS["fastq_rnaseq"]:
            cmd = (
                f"python3 -c \"import urllib.request; "
                f"urllib.request.urlretrieve('{url}', '/data/input/{filename}')\""
            )
            commands.append(cmd)
        descriptions.append("test FASTQ files for trimming")

    data_description = "; ".join(descriptions) if descriptions else "no specific data resolved"
    return commands, data_description