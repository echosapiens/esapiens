# RNA Quantification

Quantify gene expression from RNA-seq data using alignment-based and alignment-free methods.

## Recommended Tools

- **Salmon**: alignment-free quantification (quasi-mapping)
- **Kallisto**: alignment-free, fast, lightweight
- **STAR**: splice-aware aligner for alignment-based workflow
- **featureCounts**: count reads per gene from BAM alignments
- **htseq-count**: Python-based read counting

## Common Workflows

### Salmon (Recommended: Fast, Accurate)

```bash
# Build transcriptome index
salmon index -t transcripts.fa -i salmon_index --type quasi -k 31

# Quantify paired-end reads
salmon quant -i salmon_index -l A \
    -1 sample_R1.fastq.gz -2 sample_R2.fastq.gz \
    -p 8 --validateMappings -o salmon_out
```

### STAR Alignment + featureCounts

```bash
# Generate genome index
STAR --runMode genomeGenerate --genomeDir star_index \
    --genomeFastaFiles genome.fa --sjdbGTFfile annotations.gtf

# Align reads
STAR --genomeDir star_index --readFilesIn R1.fq.gz R2.fq.gz \
    --readFilesCommand zcat --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix sample_

# Count reads per gene
featureCounts -a annotations.gtf -o counts.txt sample_Aligned.sortedByCoord.out.bam
```

### Python: Load Quantification Results

```python
import pandas as pd

# Load Salmon output
df = pd.read_csv("salmon_out/quant.sf", sep="\t")
print(df[["Name", "TPM", "NumReads"]].head())

# Load featureCounts output
counts = pd.read_csv("counts.txt", sep="\t", comment="#")
```

## Key Parameters

- `-l A`: Salmon auto-detect library type
- `--validateMappings`: more accurate Salmon quantification
- `--gcBias`: correct GC bias in Salmon
- `-p`: threads for parallelization
- For DE analysis, use tximport to convert Salmon/Kallisto output for DESeq2

## Gotchas

- Use transcriptome (not genome) indices for alignment-free tools
- strandedness matters; if unknown, let Salmon auto-detect with `-l A`
- TPM is for within-sample comparison; use DESeq2/edgeR for between-sample
- Multi-mapped reads require different handling in featureCounts vs Salmon
- Always check fragmentation and strandedness from FastQC/RSeQC before quantification