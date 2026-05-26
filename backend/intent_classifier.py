"""
Intent Classifier — Maps user queries to bioSkill categories.

Simplified port from Sprint-1. The agent uses intent classification
to determine which skill context to load dynamically.
"""

import re
from typing import Optional


# Keyword → bioSkill category mapping (abridged from Sprint-1)
INTENT_KEYWORDS: dict[str, list[str]] = {
    # ---- Structural biology ----
    "structural-biology/structure-io": [
        "pdb", "structure", "chain", "chains", "residue", "residues",
        "atom", "atoms", "download", "parse", "mmcif", "cif", "pdb file",
        "protein structure", "biounit", "model", "helix", "sheet",
    ],
    "structural-biology/geometric-analysis": [
        "distance", "distances", "contact", "contacts", "within", "angstrom",
        "rmsd", "superimpose", "align", "angle", "dihedral", "neighbor",
        "sasa", "surface", "buried", "exposed",
    ],
    "structural-biology/alphafold-predictions": [
        "alphafold", "af3", "plddt", "pae", "prediction", "confidence",
        "predicted structure", "esmfold", "chai", "boltz",
    ],
    # ---- Sequence analysis ----
    "sequence-io": [
        "sequence", "sequences", "fasta", "uniprot", "accession",
        "protein sequence", "dna sequence", "rna sequence",
    ],
    "sequence-manipulation": [
        "reverse complement", "translate", "transcribe", "codon",
        "reverse", "complement", "protein translation",
    ],
    "alignment": [
        "alignment", "alignments", "multiple sequence", "msa",
        "clustal", "muscle", "global alignment", "local alignment",
    ],
    # ---- Variant analysis ----
    "variant-calling": [
        "variant", "variants", "snp", "snv", "mutation", "mutations",
        "variant calling", "variant discovery",
    ],
    "variant-calling/vcf-basics": ["vcf", "vcf file", "variant call format", "bcf", "bgzip"],
    "variant-calling/variant-annotation": [
        "annotate variant", "rsid", "dbsnp", "clinvar", "variant effect",
    ],
    "variant-calling/clinical-interpretation": [
        "clinical variant", "pathogenic", "benign", "vus", "acmg",
        "clinical interpretation", "variant classification",
    ],
    # ---- Expression & transcriptomics ----
    "rna-quantification": [
        "expression", "transcript", "fpkm", "tpm", "counts", "gene expression",
        "rna seq", "rnaseq", "quantify", "abundance",
    ],
    "differential-expression": [
        "differential expression", "de analysis", "deseq", "edger", "limma",
        "upregulated", "downregulated", "volcano plot",
    ],
    # ---- Genome assembly & mapping ----
    "read-alignment": [
        "align reads", "bwa", "bowtie", "star", "sam", "bam",
        "read mapping", "mapping",
    ],
    "read-qc": [
        "quality control", "fastqc", "qc", "read quality", "adapter",
        "trim", "trimming",
    ],
    # ---- Epigenetics ----
    "methylation-analysis": [
        "methylation", "bisulfite", "bs-seq", "methyl-seq", "5mc",
        "epigenetic", "dna methylation", "wgbs",
    ],
    # ---- Functional genomics ----
    "chip-seq": ["chip-seq", "chip", "histone", "peak calling", "binding site"],
    "atac-seq": ["atac-seq", "atac", "chromatin accessibility", "open chromatin"],
    # ---- Comparative & population genomics ----
    "phylogenetics": [
        "phylogeny", "phylogenetic", "tree", "newick", "raxml", "iqtree",
    ],
    "population-genetics": [
        "population genetics", "fst", "heterozygosity", "selection",
    ],
    # ---- Microbiome ----
    "metagenomics": [
        "metagenomics", "metagenome", "shotgun", "microbiome",
        "taxonomic profiling",
    ],
    "microbiome": [
        "microbiome", "microbiota", "bacteria", "16s", "amplicon",
    ],
    # ---- Proteomics ----
    "proteomics": [
        "proteomics", "protein", "peptides", "mass spectrometry",
        "lc-ms", "protein identification",
    ],
    # ---- Pathway & functional analysis ----
    "pathway-analysis": [
        "pathway", "enrichment", "go", "gene ontology", "kegg",
        "reactome", "biological process",
    ],
    "database-access": ["database", "query database", "retrieve", "public database"],
    "database-access/interaction-databases": [
        "interaction", "ppi", "string", "biogrid", "network",
        "protein protein", "binding partner",
    ],
    # ---- Single-cell ----
    "single-cell": [
        "single cell", "single-cell", "scrna-seq", "seurat", "scanpy",
        "cell type", "umap", "tsne",
    ],
    # ---- CRISPR ----
    "crispr-screens": [
        "crispr", "crispr screen", "cas9", "guide rna", "grna",
        "screen analysis", "mageck",
    ],
    # ---- Machine learning ----
    "machine-learning": [
        "machine learning", "ml", "deep learning", "neural network",
        "classifier", "regression", "random forest", "svm",
        "train model", "prediction model",
    ],
    # ---- Clinical ----
    "clinical-biostatistics": [
        "clinical trial", "biostatistics", "p-value", "hypothesis test",
        "anova", "t-test", "sample size",
    ],
    # ---- Data visualization & Design ----
    "ui_ux": [
        "ui", "ux", "design", "user interface", "user experience", "user story",
        "mockup", "wireframe", "frontend", "responsive", "8pt grid",
        "typography", "visual hierarchy", "color palette", "microcopy",
    ],
    "data-visualization": [
        "visualize", "plot", "chart", "graph", "heatmap", "volcano",
        "pca plot", "manhattan plot", "pretty", "beautiful", "aesthetic",
        "publication-quality", "prettier", "better plot", "nice plot",
        "matplotlib", "seaborn", "plotly", "interactive plot",
    ],
    # ---- Primer design ----
    "primer-design": [
        "primer", "pcr", "polymerase chain reaction", "qpcr",
        "amplify", "pcr design", "oligo",
    ],
    # ---- Chemoinformatics ----
    "chemoinformatics": [
        "ligand", "smiles", "similarity", "scaffold", "molecule",
        "compound", "drug", "small molecule", "rdkit", "tanimoto",
    ],
}


class IntentClassifier:
    """Classifies user queries to determine which bioSkills to load."""

    def __init__(self):
        self._patterns: dict[str, re.Pattern] = {}
        for category, keywords in INTENT_KEYWORDS.items():
            pattern = "|".join(re.escape(kw) for kw in keywords)
            self._patterns[category] = re.compile(pattern, re.IGNORECASE)

    def classify(self, query: str) -> list[str]:
        """Return list of skill categories matching the query."""
        query_lower = query.lower()
        matched: list[str] = []
        for category, pattern in self._patterns.items():
            if pattern.search(query_lower):
                matched.append(category)

        # Fallback: if nothing matched but query contains a PDB-like ID
        if not matched and re.search(r"\b[0-9][0-9a-z]{3}\b", query_lower):
            matched.append("structural-biology/structure-io")

        return matched

    def get_confidence(self, query: str, skill: str) -> float:
        """Confidence score (0.0–1.0) for a specific skill match."""
        if skill not in INTENT_KEYWORDS:
            return 0.0
        query_lower = query.lower()
        keywords = INTENT_KEYWORDS[skill]
        if not keywords:
            return 0.0
        matched = sum(1 for kw in keywords if kw.lower() in query_lower)
        return matched / len(keywords)


# Global singleton
_classifier: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def classify_query(query: str) -> list[str]:
    """Convenience: classify a query and return matched skill paths."""
    return get_classifier().classify(query)