# DNA Methylation Analysis

Analyze bisulfite sequencing (WGBS, RRBS) and array-based methylation data.

## Recommended Tools

- **Bismark**: bisulfite read alignment and methylation extraction
- **MethylDackel**: fast methylation extraction from BAM files
- **bsseq** (R/Bioconductor): smooth DMR detection
- **DSS** (R/Bioconductor): dispersive shrinkage for DMRs
- **minfi** (R/Bioconductor): Illumina 450K/EPIC array analysis

## Common Workflows

### Bismark Alignment and Methylation Calling

```bash
# Build bisulfite index
bismark_genome_preparation --path_to_bowtie2 /usr/bin/ genome_index/

# Align WGBS reads
bismark --genome genome_index/ -1 R1.fq.gz -2 R2.fq.gz \
    -p 8 --output_dir bismark_out/

# Extract methylation calls
bismark_methylation_extractor --bedGraph --CX \
    -p 8 bismark_out/*.bam

# Deduplicate
deduplicate_bismark bismark_out/*.bam
```

### DMR Detection with DSS

```r
library(DSS)

# From Bismark coverage files
bs <- BSseq(d = meth_matrix, M = total_matrix, chr = chroms, pos = positions)
dmls <- DMLfit.multiFactor(bs, design=model.matrix(~condition, coldata))
dmrs <- DMRfit.multiFactor(dmls, p.threshold=0.001)
```

### Python: Parse Methylation Data

```python
import pandas as pd

# Bismark coverage file
cov = pd.read_csv("methylation.coverage", sep="\t",
    header=None, names=["chr","pos","strand","methylated","unmethylated","context"])

cov["methylation_pct"] = cov["methylated"] / (cov["methylated"] + cov["unmethylated"]) * 100
print(cov.groupby("context")["methylation_pct"].describe())
```

## Key Parameters

- `--non_directional`: for non-directional library prep
- `--bedGraph`: produce bedGraph output
- Minimum 5x coverage for reliable CpG methylation calls
- DMR minimum width: 500bp, minimum CpGs: 5, mean difference > 25%

## Gotchas

- Bisulfite conversion efficiency should be > 99%; check lambda spike-in
- CHG/CHH methylation in plants is real; in mammals expect near-zero non-CpG
- Positional bias: 5' end of reads has lower conversion; trim 8-10bp
- RRBS enriches CpG islands; do not compare WGBS and RRBS methylation globally
- Duplicate removal is critical for WGBS (use deduplicate_bismark)