# Differential Expression Analysis

Identify genes differentially expressed between conditions using count-based statistical methods.

## Recommended Tools

- **DESeq2** (R): negative binomial GLM, most widely used
- **edgeR** (R): exact test and GLM approaches, good for small samples
- **limma-voom** (R): precision weights, good for large datasets
- **pydeseq2** (Python): Python port of DESeq2
- **deseq2**: via rpy2 for Python workflows

## Common Workflows

### DESeq2 in R

```r
library(DESeq2)

# From count matrix
counts <- as.matrix(read.csv("counts.csv", row.names=1))
coldata <- read.csv("coldata.csv", row.names=1)

dds <- DESeqDataSetFromMatrix(countData=counts, colData=coldata, design=~condition)
dds <- DESeq(dds)

# Results
res <- results(dds, contrast=c("condition", "treated", "control"))
res <- lfcShrink(dds, coef="condition_treated_vs_control", type="apeglm")

# Export
write.csv(as.data.frame(res), "deseq2_results.csv")
```

### PyDESeq2 (Python)

```python
from pydeseq2.DeseqDataSet import DeseqDataSet
from pydeseq2.DeseqStats import DeseqStats
import pandas as pd

counts = pd.read_csv("counts.csv", index_col=0)
metadata = pd.read_csv("coldata.csv", index_col=0)

dds = DeseqDataSet(counts=counts, metadata=metadata, design_factors="condition")
dds.run_deseq()
stats = DeseqStats(dds)
stats.summary()
results = stats.results_df
```

### Volcano Plot

```python
import matplotlib.pyplot as plt
import numpy as np

def volcano(results_df, lfc_col="log2FoldChange", pval_col="padj", threshold=0.05):
    results_df["-log10(padj)"] = -np.log10(results_df[pval_col])
    sig = results_df["padj"] < threshold
    plt.figure(figsize=(10, 8))
    plt.scatter(results_df[~sig][lfc_col], results_df[~sig]["-log10(padj)"],
                alpha=0.3, s=5, color="gray")
    plt.scatter(results_df[sig][lfc_col], results_df[sig]["-log10(padj)"],
                alpha=0.5, s=8, color="red")
    plt.axhline(-np.log10(threshold), color="blue", linestyle="--", alpha=0.5)
    plt.axvline(-1, color="blue", linestyle="--", alpha=0.5)
    plt.axvline(1, color="blue", linestyle="--", alpha=0.5)
    plt.xlabel("log2 Fold Change")
    plt.ylabel("-log10 adjusted p-value")
    plt.title("Volcano Plot")
    plt.savefig("volcano.png", dpi=300)
```

## Key Parameters

- Minimum replicates: 3 per condition recommended (minimum 2)
- `lfcShrink` with `apeglm` for shrunken log2FC estimates
- Use `padj` (Benjamini-Hochberg) not raw p-values for significance
- Typical thresholds: |log2FC| > 1 and padj < 0.05

## Gotchas

- Low-count genes should be filtered (rowSums < 10) before analysis
- DESeq2 automatically handles size factor normalization; do not provide RPM/TPM
- batch effects must be included in the design formula: `~ batch + condition`
- Independent filtering removes low-count genes; check `results$baseMean`
- Cook's distance outliers: DESeq2 flags but does not remove them by default