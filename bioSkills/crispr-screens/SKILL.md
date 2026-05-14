# CRISPR Screen Analysis

Analyze CRISPR knockout/activation screen data for gene essentiality and drug target discovery.

## Recommended Tools

- **MAGeCK**: Model-based Analysis of Genome-wide CRISPR-Cas9 Knockout
- **MAGeCK-VISPR**: quality control and visualization for screens
- **MAGeCK-Flute**: downstream analysis and normalization
- **CRISPResso2**: CRISPR editing outcome quantification
- **PinAPL-Py**: web-based CRISPR analysis pipeline

## Common Workflows

### MAGeCK Count and Test

```bash
# Generate read counts from FASTQ
mageck count -l library.txt -n sample1 \
    --fastq sample1_R1.fastq.gz \
    --fastq-2 sample1_R2.fastq.gz

# Differential analysis (treatment vs control)
mageck test -k counts.txt -t treatment_rep1,treatment_rep2 \
    -c control_rep1,control_rep2 \
    -n mageck_results --gene-lfc-file gene_lfc.txt

# Output: gene_summary.txt with RRA p-values, log2 fold changes
```

### Python: Process MAGeCK Results

```python
import pandas as pd

# Load gene-level results
results = pd.read_csv("mageck_results.gene_summary.txt", sep="\t")
significant = results[(results["pval"] < 0.05) & (results["pval"] < 0.05)]

# Essential genes (negative selection)
essential = results[results["neg|lfc"] < -1].sort_values("neg|p-value")
print(f"Essential genes: {len(essential)}")

# Enriched genes (positive selection / resistance)
enriched = results[results["pos|lfc"] > 1].sort_values("pos|p-value")
print(f"Enriched genes: {len(enriched)}")
```

### Quality Control

```bash
# Mapping rate and GC bias
mageck qc -k counts.txt -n qc_report

# Check: mapping rate > 70%, Gini index < 0.1 for good library representation
# Zero-count sgRNAs should be < 1% of total
```

## Key Parameters

- Minimum 300x coverage per sgRNA for knockout screens
- MAGeCK RRA algorithm: robust rank aggregation for gene-level significance
- `--norm-method median`: median normalization (default)
- `--control-sgrna`: non-targeting controls for normalization
- For essential gene screens: use DepMap/Achilles as validation reference

## Gotchas

- Library representation is critical; Gini index > 0.1 indicates poor representation
- Always include non-targeting controls (NTC sgRNAs) for normalization
- Guide-level analysis before gene-level aggregation reveals off-target effects
- CRISPRi/a screens have different analysis requirements than knockout screens
- Copy number bias: amplify gene-level signals in amplified regions; use CRISPRcleanR to correct