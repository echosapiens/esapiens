# Sequence I/O

Reading, writing, and converting biological sequence files across standard formats (FASTA, GenBank, EMBL, GFF3, FASTQ).

## Description

Sequence I/O covers loading and saving nucleotide and protein sequences in common bioinformatics formats. This includes FASTA (most common), FASTQ (with quality scores), GenBank/EMBL (with rich annotation), and GFF3/GTF (feature annotations). Reliable I/O is the foundation for every sequence analysis pipeline.

## Recommended Tools

### Python Packages
- **BioPython** (`Bio.SeqIO`): Universal sequence I/O supporting 20+ formats
- **BioPython** (`Bio.SeqRecord`): Sequence record objects with annotations
- **pyfaidx**: Fast random access to FASTA files by indexed lookup
- **pysam**: FASTA/FASTQ I/O with BAM/VCF integration
- **biopython-seq**: Accelerated sequence operations
- **dnaio**: Fast FASTA/FASTQ parser (used by Cutadapt)

### CLI Tools
- **seqkit**: Ultra-fast FASTA/Q manipulation toolkit
- **samtools faidx**: FASTA indexing and random access
- **grep/sed/awk**: Quick filtering on FASTA files
- **EMBOSS seqret**: Format conversion across 30+ sequence formats

### Databases
- NCBI Entrez/RefSeq: Programmatic sequence retrieval
- UniProt: Protein sequence downloads (FASTA, XML, RDF)
- Ensembl REST API: Genome sequence retrieval by region

## Common Workflows

### Read and write FASTA with BioPython

```python
from Bio import SeqIO

# Read all records from a FASTA file
records = list(SeqIO.parse("genes.fasta", "fasta"))
print(f"Loaded {len(records)} sequences")

# Iterate without loading all into memory
for record in SeqIO.parse("large_database.fasta", "fasta"):
    if len(record.seq) > 1000:
        print(f"{record.id}: {len(record.seq)} bp")

# Write selected records
SeqIO.write(records[:10], "subset.fasta", "fasta")
```

### Index a large FASTA for random access

```python
from Bio import SeqIO

# Build an index (does not load all sequences into memory)
idx = SeqIO.index("genome.fa", "fasta")

# Retrieve a specific sequence by ID
chromosome = idx["chr1"]
print(f"chr1 length: {len(chromosome.seq)} bp")

# Slice a region
region = chromosome.seq[999999:1001000]  # 0-based
print(region)

idx.close()
```

### Fast random access with pyfaidx

```python
from pyfaidx import Fasta

genome = Fasta("genome.fa", as_raw=True)  # as_raw returns strings, not SeqRecords
sequence = genome["chr1"][999999:1001000]

# Also supports line-based indexing for very large files
```

### Read FASTQ with quality scores

```python
from Bio import SeqIO

for record in SeqIO.parse("reads.fastq", "fastq"):
    # record.letter_annotations["phred_quality"] contains quality scores
    quals = record.letter_annotations["phred_quality"]
    mean_qual = sum(quals) / len(quals)
    if mean_qual >= 30:
        print(f"{record.id}: mean Q{mean_qual:.1f}")
```

### Parse GenBank files with annotations

```python
from Bio import SeqIO

record = SeqIO.read("sequence.gb", "genbank")
print(f"Organism: {record.annotations['organism']}")
print(f"Topology: {record.annotations['topology']}")

for feature in record.features:
    if feature.type == "CDS":
        gene = feature.qualifiers.get("gene", ["?"])[0]
        product = feature.qualifiers.get("product", [""])[0]
        print(f"  {gene}: {feature.location} -> {product}")
```

### Download sequences from NCBI

```python
from Bio import Entrez, SeqIO

Entrez.email = "researcher@example.org"

def fetch_fasta(accession: str) -> str:
    """Fetch a sequence from NCBI in FASTA format."""
    handle = Entrez.efetch(
        db="nucleotide", id=accession, rettype="fasta", retmode="text"
    )
    record = SeqIO.read(handle, "fasta")
    handle.close()
    return record

def fetch_genbank(accession: str):
    """Fetch a GenBank record with full annotations."""
    handle = Entrez.efetch(
        db="nucleotide", id=accession, rettype="gb", retmode="text"
    )
    record = SeqIO.read(handle, "genbank")
    handle.close()
    return record
```

### Format conversion with seqkit

```bash
# GenBank to FASTA
seqkit seq2fasta input.gb -o output.fasta

# FASTQ to FASTA (strip quality)
seqkit fasta input.fastq -o output.fasta

# Extract sequences by ID list
seqkit grep -f ids.txt sequences.fasta -o matched.fasta

# Get sequence lengths
seqkit stats sequences.fasta
```

### Parse GFF3 annotation files

```python
from BCBio import GFF

with open("annotations.gff3") as handle:
    for record in GFF.parse(handle):
        for feature in record.features:
            if feature.type == "gene":
                print(f"Gene: {feature.id} at {feature.location}")
```

## Key Parameters and Gotchas

### Format-Specific Issues
- **FASTA wrapping**: Line length varies (60, 70, 80 characters). Always use a proper parser, not line-by-line string concatenation.
- **FASTQ encoding**: Most modern data uses Sanger/Illumina 1.8+ (Phred+33). Older Illumina data used Phred+64. BioPython auto-detects, but verify with `record.letter_annotations["phred_quality"]` values.
- **GenBank vs EMBL**: Same content, different delimiters. BioPython handles both transparently.
- **GFF3 vs GTF**: GFF3 is the standard; GTF (GTF2.2) is a legacy format used by ENSEMBL. Column 9 (attributes) syntax differs significantly.

### Common Pitfalls
- **Memory**: Loading an entire genome FASTA into memory with `list(SeqIO.parse(...))` can exhaust RAM. Use `SeqIO.index()` for large files.
- **Sequence IDs**: FASTA headers may contain spaces, pipes, or other delimiters. The ID is typically everything before the first whitespace, but conventions vary (UniProt uses `|db|accession|entry_name`).
- **Strand**: GenBank features on the minus strand have `feature.location.strand == -1`. The sequence is always 5' to 3' on the reference strand; reverse complement for gene sequences.
- **Partial features**: Features spanning origin in circular genomes or with `>` / `<` operators need special handling.
- **NCBI rate limits**: Entrez requests should include a tool name and email. Limit to ~3 requests/second without an API key; ~10/second with one.
- **Encoding**: FASTQ files may contain non-ASCII quality characters. Always open in text mode with proper encoding.
