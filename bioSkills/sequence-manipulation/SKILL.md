# Sequence Manipulation

Transforming, filtering, and modifying biological sequences including reverse complement, translation, trimming, masking, and composition analysis.

## Description

Sequence manipulation covers common operations on nucleotide and protein sequences: reverse complement, translation (with genetic code selection), codon optimization, sequence masking (dust, repeatmasker), trimming, extraction of subsequences, and composition analysis (GC content, k-mer counts, ORF detection). These operations are building blocks for pipeline development.

## Recommended Tools

### Python Packages
- **BioPython** (`Bio.Seq`, `Bio.SeqUtils`): Core sequence operations and utilities
- **Biopython** (`Bio.Data.CodonTable`): Genetic code tables for translation
- **pydna**: DNA sequence manipulation for cloning simulation
- **dna_features_viewer**: Visualization of sequence features
- **skbio** (`skbio.sequence`): K-mer counting and sequence statistics
- **DnaChisel**: Codon optimization and sequence design with constraints

### CLI Tools
- **seqkit**: Sequence transformation, filtering, and statistics
- **EMBOSS**: `revseq`, `transeq`, `getorf`, `geecee`, `maskseq`
- **dustmasker**: Low-complexity masking for nucleotide sequences
- **segmasker**: Low-complexity masking for protein sequences
- **RepeatMasker**: Repeat element identification and masking

## Common Workflows

### Reverse complement and translation

```python
from Bio.Seq import Seq

dna = Seq("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG")

# Reverse complement
rc = dna.reverse_complement()
print(f"RevComp: {rc}")

# Translation (standard genetic code)
protein = dna.translate()
print(f"Protein: {protein}")

# Translation with stop codon handling
protein_full = dna.translate(to_stop=True)  # Stop at first stop codon
protein_partial = dna.translate(cds=True)   # Expect start->stop, raise error otherwise

# Alternative genetic codes (mitochondrial, etc.)
protein_mt = dna.translate(table="Vertebrate Mitochondrial")
```

### GC content and sequence composition

```python
from Bio.SeqUtils import gc_fraction
from Bio.Seq import Seq

seq = Seq("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG")
gc = gc_fraction(seq)  # Returns float 0-1
print(f"GC content: {gc:.2%}")

# Manual calculation for more control
def composition(seq: str) -> dict:
    """Count nucleotide frequencies."""
    seq = seq.upper()
    return {base: seq.count(base) / len(seq) for base in "ATGCN"}

comp = composition(str(seq))
for base, freq in comp.items():
    print(f"  {base}: {freq:.3f}")
```

### K-mer counting

```python
from collections import Counter
from itertools import product

def kmer_count(sequence: str, k: int) -> Counter:
    """Count all k-mers in a sequence."""
    sequence = sequence.upper()
    return Counter(sequence[i:i+k] for i in range(len(sequence) - k + 1))

def kmer_frequency(sequence: str, k: int, normalize: bool = True) -> dict:
    """Compute k-mer frequencies, optionally normalized."""
    counts = kmer_count(sequence, k)
    total = sum(counts.values())
    if normalize:
        return {kmer: count / total for kmer, count in counts.items()}
    return dict(counts)

# Generate all possible k-mers
def all_kmers(k: int) -> list[str]:
    return ["".join(p) for p in product("ACGT", repeat=k)]

kmers_4 = kmer_frequency("ATGGCCATTGTAATGGGCCGCTGAAAGGG", 4)
```

### ORF detection

```python
from Bio.Seq import Seq

def find_orfs(sequence: Seq, min_length: int = 300, table: int = 1) -> list[dict]:
    """Find open reading frames on both strands."""
    orfs = []
    for strand, seq in [(+1, sequence), (-1, sequence.reverse_complement())]:
        for frame in range(3):
            protein = seq[frame:].translate(table=table)
            start = 0
            while start < len(protein):
                # Find start codon (M)
                try:
                    start = protein.index("M", start)
                except ValueError:
                    break
                # Find stop codon
                try:
                    stop = protein.index("*", start)
                except ValueError:
                    break
                orf_len = (stop - start + 1) * 3
                if orf_len >= min_length:
                    orfs.append({
                        "start": frame + start * 3,
                        "end": frame + (stop + 1) * 3,
                        "strand": strand,
                        "length": orf_len,
                        "protein": str(protein[start:stop]),
                    })
                start = stop + 1
    return orfs

orfs = find_orfs(Seq("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG"), min_length=30)
for orf in orfs:
    print(f"ORF: {orf['start']}-{orf['end']} ({orf['strand']}) {orf['length']} bp")
```

### Sequence masking

```python
from Bio.Seq import Seq

def mask_low_complexity(sequence: str, window: int = 12, threshold: float = 0.7) -> str:
    """Simple low-complexity masking: replace runs of same nucleotide."""
    seq = list(sequence.upper())
    for base in "ACGT":
        i = 0
        while i < len(seq):
            if seq[i] == base:
                run_start = i
                while i < len(seq) and seq[i] == base:
                    i += 1
                run_len = i - run_start
                if run_len >= window:
                    for j in range(run_start, i):
                        seq[j] = seq[j].lower()
            else:
                i += 1
    return "".join(seq)
```

### Batch sequence manipulation with seqkit

```bash
# Reverse complement all sequences
seqkit seq -r -p sequences.fasta -o rc.fasta

# Translate nucleotide to protein
seqkit translate sequences.fasta -o proteins.fasta

# Extract subsequences (0-based, half-open)
seqkit subseq -r 100:500 sequences.fasta -o regions.fasta

# Remove gaps from alignment
seqkit seq -g aligned.fasta -o ungapped.fasta

# Filter by sequence length
seqkit seq -m 100 -M 1000 sequences.fasta -o filtered.fasta

# Shuffle sequence order
seqkit shuffle sequences.fasta -o shuffled.fasta

# Compute GC content
seqkit fx2tab -n -g -H sequences.fasta > gc_content.tsv
```

### Codon optimization with DnaChisel

```python
from dnachisel import DnaOptimizationProblem, CodonOptimize, AvoidPattern

problem = DnaOptimizationProblem(
    sequence="ATGGCCATTGTAATGGGCCGCTGA",
    constraints=[AvoidPattern("BsaI_site")],
    objectives=[CodonOptimize(species="e_coli")],
)
problem.resolve_constraints()
problem.optimize()
print(problem.sequence)
```

## Key Parameters and Gotchas

### Translation
- **Genetic codes**: NCBI defines 33 genetic codes. The standard code is table 1. Vertebrate mitochondrial is table 2. Always specify the table for non-standard organisms.
- **Partial ORFs**: Sequences may not start with ATG or end with a stop codon. Use `translate()` without `cds=True` for partial sequences.
- **Selenocysteine**: The codon TGA is normally a stop but encodes selenocysteine (U) in specific contexts. Standard translation will call it a stop.

### Composition Analysis
- **GC content ambiguity**: N characters in sequences affect GC calculation. `gc_fraction()` excludes N by default. Be explicit about how N is handled.
- **K-mer normalization**: Frequency normalization by total k-mer count can be misleading for sequences of very different lengths. Consider using pseudocounts.

### Masking
- **Soft masking** (lowercase) preserves the sequence for alignment but signals low complexity. BLAST and many aligners respect soft masking.
- **Hard masking** (replaced with N) removes information entirely. Use only when low-complexity regions cause spurious alignments.
- **Dustmasker** is faster than RepeatMasker for simple low-complexity detection. RepeatMasker is needed for transposable element annotation.

### Common Pitfalls
- **Strand convention**: `Seq.reverse_complement()` returns a new Seq object on the opposite strand. Do not forget to reverse complement when extracting coding sequences from minus-strand features.
- **Coordinate systems**: Python uses 0-based indexing. GenBank/GFF use 1-based. FASTA subsequence extraction requires careful offset handling.
- **Ambiguity codes**: IUPAC codes (R, Y, S, W, etc.) represent degenerate positions. Translation of ambiguity codes may produce X in protein sequences.
- **Case sensitivity**: Masked sequences mix upper and lowercase. Most tools treat them equivalently for alignment but differently for pattern matching.
