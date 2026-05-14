# Proteomics

Analyze mass spectrometry-based proteomics data for protein identification and quantification.

## Recommended Tools

- **MaxQuant**: identification and quantification (LFQ, TMT, SILAC)
- **MSFragger**: ultra-fast database search engine
- **Perseus**: downstream statistical analysis of MaxQuant output
- **PyMS**: Python proteomics framework
- **matchms**: Python spectral similarity analysis
- **pyopenms**: Python bindings for OpenMS algorithms

## Common Workflows

### MaxQuant (GUI/CLI)

Configure in MaxQuant GUI:
1. Load raw files (.raw, .mzML)
2. Set enzyme: Trypsin/P, max missed cleavages: 2
3. Set modifications: Carbamidomethyl (C) fixed, Oxidation (M) variable
4. Set quantification: LFQ or TMT
5. Set FDR: 1% PSM and protein level
6. Run and process output in Perseus

### Python: Extract Protein Intensities

```python
import pandas as pd

# MaxQuant protein groups output
pg = pd.read_csv("proteinGroups.txt", sep="\t", low_memory=False)

# Filter: remove contaminants, reverse hits, only identified by site
pg = pg[~pg["Potential contaminant"].astype(bool)]
pg = pg[~pg["Reverse"].astype(bool)]
pg = pg[pg["Peptides"] >= 2]  # minimum 2 peptides

# Get LFQ intensities
lfq_cols = [c for c in pg.columns if "LFQ intensity" in c]
intensities = pg[["Protein IDs", "Gene names"] + lfq_cols]
```

### TMT Quantification Analysis

```python
import numpy as np

# Reporter ion intensities from MSFragger/TPP
tmt_data = pd.read_csv("tmt_ratios.tsv", sep="\t")

# Normalize: median scaling
for col in tmt_cols:
    tmt_data[col] = tmt_data[col] / np.median(tmt_data[col].dropna())

# Log2 fold change
tmt_data["log2FC"] = np.log2(tmt_data["treatment"] / tmt_data["control"])
tmt_data["-log10p"] = -np.log10(tmt_data["pvalue"])
```

## Key Parameters

- PSM FDR: 1%, Protein FDR: 1%
- Minimum 2 unique peptides per protein identification
- LFQ min ratio count: 2 (MaxQuant)
- TMT: reporter ion mass tolerance 0.003 Da

## Gotchas

- Protein inference: shared peptides cause protein group ambiguity
- Always filter contaminants, reverse database hits
- LFQ imputation: replace missing values with normal distribution (width=0.3, downshift=1.8)
- TMT ratio compression: use SPS-MS3 or real-time search to mitigate
- Raw file conversion: msconvert (ProteoWizard) for vendor format to mzML