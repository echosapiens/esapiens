# Metagenomics

Analyze shotgun metagenomic sequencing data for taxonomic profiling and functional annotation.

## Recommended Tools

- **Kraken2**: fast k-mer based taxonomic classification
- **Bracken**: Bayesian re-estimation of Kraken2 abundances
- **MetaPhlAn3**: marker gene-based profiling (more precise)
- **HUMAnN3**: functional profiling (pathway/gene family abundances)
- **MEGAHIT / metaSPAdes**: metagenome assembly
- **CheckM2**: assess metagenome-assembled genome (MAG) quality

## Common Workflows

### Taxonomic Profiling with Kraken2 + Bracken

```bash
# Build database (one-time, large)
kraken2-build --download-db --db kraken_db

# Classify reads
kraken2 --db kraken_db --paired R1.fq.gz R2.fq.gz \
    --threads 8 --output classified.tsv --report report.tsv

# Re-estimate abundances with Bracken
bracken -d kraken_db -i report.tsv -o bracken_report.tsv \
    -l S -r 100 -t 8
```

### MetaPhlAn3 Profiling

```bash
metaphlan R1.fq.gz,R2.fq.gz --input_type fastq \
    --nproc 8 -o profile.tsv --bowtie2db metaphlan_db/
```

### Functional Profiling with HUMAnN3

```bash
humann --input R1.fq.gz --output humann_out/ --threads 8
# Produces: gene families (UniRef90), pathway abundances, pathway coverage
```

### Python: Parse Taxonomic Profile

```python
import pandas as pd

# Kraken2 report
report = pd.read_csv("report.tsv", sep="\t",
    names=["pct","reads","reads_lvl","code","taxid","name"])

# Filter to species level
species = report[report["code"] == "S"]
print(species[["pct","name"]].sort_values("pct", ascending=False).head(10))
```

## Key Parameters

- Kraken2: `--confidence 0.1` to reduce false positives
- Bracken: `-r 100` for 100bp read length; set to actual read length
- MetaPhlAn3: use `--input_type fastq` for raw reads
- Minimum 5M reads per sample for reasonable taxonomic coverage

## Gotchas

- Kraken2 database is 50-100GB; use pre-built or build on high-memory machine
- Bracken re-estimation is essential; raw Kraken2 counts are biased
- MetaPhlAn3 is marker-based and more precise but less sensitive than Kraken2
- Host contamination (human DNA) should be filtered before profiling
- For low-biomass samples, include negative controls to detect reagent contamination