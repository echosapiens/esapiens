# Primer Design

Design PCR primers for amplification, Sanger sequencing, and qPCR assays.

## Recommended Tools

- **Primer3**: gold standard primer design engine
- **Primer-BLAST** (NCBI web): design primers with specificity check
- **Biopython Bio.SeqUtils**: melting temperature, GC content
- **OligoAnalyzer** (IDT): thermodynamic properties
- **ecoprimer**: in silico PCR with specificity check

## Common Workflows

### Primer3 Computationally

```python
from primer3 import bindings

# Design primers for a target region
seq_template = "ATCGATCGATCG..."  # your sequence
result = bindings.design_primers(
    seq_args={
        "SEQUENCE_ID": "target_gene",
        "SEQUENCE_TEMPLATE": seq_template,
        "SEQUENCE_INCLUDED_REGION": [0, len(seq_template)],
    },
    global_args={
        "PRIMER_OPT_SIZE": 20,
        "PRIMER_MIN_SIZE": 18,
        "PRIMER_MAX_SIZE": 25,
        "PRIMER_OPT_TM": 60.0,
        "PRIMER_MIN_TM": 57.0,
        "PRIMER_MAX_TM": 63.0,
        "PRIMER_MIN_GC": 40.0,
        "PRIMER_MAX_GC": 60.0,
        "PRIMER_MAX_POLY_X": 4,
        "PRIMER_NUM_RETURN": 5,
        "PRIMER_PRODUCT_SIZE_RANGE": [[100, 300]],
    }
)

for i in range(result.get("PRIMER_PAIR_NUM_RETURNED", 0)):
    print(f"Pair {i+1}:")
    print(f"  Fwd: {result[f'PRIMER_LEFT_{i}_SEQUENCE']} (Tm={result[f'PRIMER_LEFT_{i}_TM']:.1f})")
    print(f"  Rev: {result[f'PRIMER_RIGHT_{i}_SEQUENCE']} (Tm={result[f'PRIMER_RIGHT_{i}_TM']:.1f})")
    print(f"  Product: {result[f'PRIMER_PAIR_{i}_PRODUCT_SIZE']}bp")
```

### Check Primer Specificity with BLAST

```python
from Bio.Blast import NCBIWWW, NCBIXML

# BLAST primer against nt database
result = NCBIWWW.qblast("blastn", "nt", primer_seq, expect=0.01)
records = NCBIXML.parse(result)
for record in records:
    for alignment in record.alignments:
        print(f"Hit: {alignment.title}, E-value: {alignment.hsps[0].expect}")
```

### Melting Temperature Calculation

```python
from Bio.SeqUtils.MeltingTemp import Tm_Wallace, Tm_NN

primer = "ATCGATCGATCGATCGATCG"
print(f"Wallace rule: {Tm_Wallace(primer):.1f} C")
print(f"Nearest-neighbor: {Tm_NN(primer, Na=50, dnac1=250, dnac2=250):.1f} C")
```

## Key Parameters

- Primer length: 18-25 bp (optimal 20 bp)
- Tm: 57-63 C (optimal 60 C); pair Tm within 2 C
- GC content: 40-60% (optimal 50%)
- Product size: 100-300 bp (qPCR), 500-2000 bp (cloning)
- Max poly-X: 4 (avoid runs of same nucleotide)
- 3' end: avoid >2 G/C in last 5 bases (reduces mispriming)

## Gotchas

- Always BLAST primers against the target organism genome for specificity
- SNPs in primer binding sites cause assay failure in population studies
- qPCR efficiency should be 90-110%; check with dilution series
- Primer-dimers detected by melt curve analysis; redesign if present
- Template secondary structure at 3' end reduces efficiency