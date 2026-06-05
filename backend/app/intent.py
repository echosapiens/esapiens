"""Simple intent classifier to distinguish casual chat from bioinformatics pipeline requests."""

# Keywords that suggest a bioinformatics pipeline request
PIPELINE_KEYWORDS = [
    "align", "sequence", "genome", "bam", "fastq", "fasta", "sam",
    "samtools", "bwa", "star", "bowtie", "hisat", "mafft", "muscle",
    "clustal", "blast", "fastqc", "trimmomatic", "salmon", "quantify",
    "rna-seq", "rna seq", "dna", "transcript", "variant", "vcf",
    "pipeline", "assembly", "trim", "index", "map", "mapping",
    "alignment", "analysis", "quantification", "expression",
    "differential", "count", "reads", "reference", "annotation",
    "download", "fastq.gz", "genbank", "pdb", "protein",
    "container", "docker", "runner", "execute", "run",
    "grch38", "grch37", "hg38", "hg19", "ensembl", "ncbi",
    "biocontainer", "quay.io",
]


def classify_intent(message: str) -> str:
    """
    Classify a user message as either 'pipeline' or 'chat'.
    
    Returns 'pipeline' if the message appears to be a bioinformatics
    pipeline request, 'chat' otherwise.
    """
    msg_lower = message.lower().strip()
    
    # Short messages are almost certainly casual chat
    if len(msg_lower.split()) <= 2:
        return "chat"
    
    # Check for pipeline keywords
    word_count = len(msg_lower.split())
    keyword_hits = sum(1 for kw in PIPELINE_KEYWORDS if kw in msg_lower)
    
    # If >=2 keywords hit, or 1 keyword in a short message, it's a pipeline request
    if keyword_hits >= 2:
        return "pipeline"
    if keyword_hits == 1 and word_count >= 3:
        return "pipeline"
    
    return "chat"