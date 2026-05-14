# Alignment

Pairwise and multiple sequence alignment for nucleotide and protein sequences, including alignment file formats, scoring, and visualization.

## Description

Sequence alignment is the fundamental operation of comparing biological sequences to identify conserved regions, infer homology, and detect functional elements. This covers pairwise alignment (local, global, semi-global), multiple sequence alignment (MSA), alignment file formats (CLUSTAL, Stockholm, PHYLIP), and assessment of alignment quality. Proper alignment is critical for phylogenetics, motif discovery, and structural modeling.

## Recommended Tools

### Python Packages
- **BioPython** (`Bio.Align`, `Bio.Align.Applications`): Alignment I/O and wrapper for external aligners
- **BioPython** (`Bio.pairwise2`): Pairwise alignment (deprecated, use `Bio.Align.PairwiseAligner`)
- **Bio.Align.PairwiseAligner**: Modern pairwise alignment with C acceleration
- **muscle3** / **muscle**: Python bindings for MUSCLE aligner
- **clustalo**: Python interface to ClustalOmega
- **pyMSA**: MSA visualization
- **logomaker**: Sequence logo visualization from MSAs

### CLI Tools
- **MAFFT**: Fast, accurate multiple alignment (--auto mode recommended)
- **MUSCLE**: Accurate MSA (v5 is much faster than v3)
- **Clustal Omega**: Scalable MSA for large datasets
- **MAFFT --add**: Adding sequences to an existing alignment
- **T-Coffee**: Structure-informed alignment
- **PRANK**: Phylogeny-aware alignment for coding sequences
- **AliView**: Interactive alignment editor

### Web Services
- EBI Clustal Omega, MAFFT, MUSCLE web interfaces
- UCSC Multiz for whole-genome alignment

## Common Workflows

### Pairwise alignment with BioPython

```python
from Bio.Align import PairwiseAligner

aligner = PairwiseAligner()
aligner.mode = "global"  # or "local"
aligner.match_score = 2.0
aligner.mismatch_score = -1.0
aligner.open_gap_score = -5.0
aligner.extend_gap_score = -0.5

seq1 = "MKWVTFISLLFLFSSAYSR"
seq2 = "MKWVTFISLLFLFSSAYSRSR"

alignments = aligner.align(seq1, seq2)
best = alignments[0]
print(f"Score: {best.score}")
print(f"Alignment:\n{best}")
```

### Multiple sequence alignment with MAFFT

```bash
# Automatic mode selection
mafft --auto input.fasta > aligned.fasta

# More accurate for divergent sequences
mafft --linsi input.fasta > aligned.fasta

# Fast for large datasets (>1000 sequences)
mafft --fftns2 input.fasta > aligned.fasta

# Add sequences to existing alignment
mafft --add new_sequences.fasta --reorder existing_alignment.fasta > updated.fasta

# Iterative refinement with local pairwise
mafft --genafpair input.fasta > aligned.fasta
```

### Multiple sequence alignment with MUSCLE

```bash
# Standard MUSCLE v5
muscle -align input.fasta -output aligned.fasta

# For very large datasets
muscle -align input.fasta -output aligned.fasta -maxiters 2

# Refine existing alignment
muscle -refine aligned.fasta -output refined.fasta
```

### Parse and analyze an MSA

```python
from Bio import AlignIO
import numpy as np

alignment = AlignIO.read("aligned.fasta", "fasta")
print(f"Sequences: {len(alignment)}")
print(f"Alignment length: {alignment.get_alignment_length()}")

# Calculate conservation per column
def column_conservation(alignment, column: int) -> float:
    """Fraction of most common residue at a column."""
    residues = [record.seq[column].upper() for record in alignment]
    residues = [r for r in residues if r != "-"]  # Exclude gaps
    if not residues:
        return 0.0
    from collections import Counter
    counts = Counter(residues)
    return counts.most_common(1)[0][1] / len(residues)

conservation = [
    column_conservation(alignment, i)
    for i in range(alignment.get_alignment_length())
]
```

### Generate a sequence logo

```python
import logomaker as lm
import pandas as pd
from Bio import AlignIO

alignment = AlignIO.read("aligned.fasta", "fasta")
# Build counts matrix
seqs = [str(rec.seq) for rec in alignment]
counts_df = lm.alignment_to_matrix(seqs)

logo = lm.Logo(counts_df, shade_below=0.5, fade_below=0.5)
logo.style_spines(visible=False)
logo.style_xticks(rotation=90, fmt="%d", anchor=0)
```

### Trim alignment to conserved regions

```bash
# Using trimAl
trimal -in aligned.fasta -out trimmed.fasta -automated1

# Remove columns with >50% gaps
trimal -in aligned.fasta -out trimmed.fasta -gt 0.5

# Using BMGE (more sophisticated)
java -jar bmge.jar -i aligned.fasta -t AA -of trimmed.fasta
```

## Key Parameters and Gotchas

### Alignment Strategy Selection
- **Global** (Needleman-Wunsch): Use when sequences are expected to be homologous end-to-end. Best for comparing orthologs of similar length.
- **Local** (Smith-Waterman): Use for finding conserved domains within longer sequences. Best for database searches and domain detection.
- **Semi-global**: Use when one sequence is expected to be a substring of the other (e.g., read mapping, primer matching).

### MSA Algorithm Selection
- **MAFFT L-INS-i** (`--linsi`): Most accurate; slow for >500 sequences. Use for publication-quality alignments.
- **MAFFT FFT-NS-2** (`--fftns2`): Fast; suitable for >1000 sequences where moderate accuracy is acceptable.
- **Clustal Omega**: Scales to tens of thousands of sequences; good for profile construction.
- **PRANK**: Phylogeny-aware; handles insertions correctly but is slow. Preferred for coding sequence alignment.
- **T-Coffee**: Can integrate structural information; useful when 3D structures are available.

### Scoring Parameters
- **Protein substitution matrices**: BLOSUM62 is the default and works well for ~30% identity. Use BLOSUM80 for close homologs, BLOSUM45 for distant.
- **Gap penalties**: Open gap penalty should be severe enough to prevent excessive gapping. Typical values: open=-10, extend=-0.5 for protein; open=-15, extend=-0.5 for nucleotide.
- **Nucleotide vs protein**: Always align protein sequences when possible, then back-translate to codons if needed. Protein alignment captures functional constraints better.

### Common Pitfalls
- **Gap placement**: Different aligners place gaps differently, especially in low-conservation regions. Always inspect and manually curate alignments for phylogenetics.
- **Alignment trimming**: Removing poorly aligned regions before phylogenetics is essential. Use trimAl or BMGE, not ad hoc filtering.
- **Sequence length heterogeneity**: Sequences of vastly different lengths (e.g., full-length vs fragment) produce poor MSAs. Filter fragments first.
- **Codon alignment**: For coding sequences, align at the protein level and then map gaps to the nucleotide sequence using `pal2nal` or `revtrans`.
- **Iteration convergence**: MAFFT and MUSCLE use iterative refinement. More iterations improve accuracy marginally but increase runtime significantly.
- **Reverse-complement**: Ensure all nucleotide sequences are on the same strand before alignment. MAFFT does not auto-orient sequences.
