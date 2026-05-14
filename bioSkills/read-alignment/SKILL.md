# Read Alignment

Map sequencing reads to a reference genome using splice-aware aligners.

## Recommended Tools

- **STAR**: fast splice-aware aligner, RNA-seq standard
- **BWA-MEM2**: fast aligner for DNA-seq (WGS, WES, ChIP-seq)
- **Bowtie2**: gapped alignment for DNA-seq
- **HISAT2**: lightweight splice-aware aligner, successor to TopHat2
- **minimap2**: long-read alignment (PacBio, Nanopore)

## Common Workflows

### STAR (RNA-seq alignment)

```bash
# Build index (one-time)
STAR --runMode genomeGenerate --genomeDir star_index \
    --genomeFastaFiles genome.fa --sjdbGTFfile annotations.gtf \
    --runThreadN 8

# Align paired-end reads
STAR --genomeDir star_index \
    --readFilesIn R1.fq.gz R2.fq.gz --readFilesCommand zcat \
    --outSAMtype BAM SortedByCoordinate \
    --outFileNamePrefix sample_ --runThreadN 8
```

### BWA-MEM2 (DNA-seq alignment)

```bash
# Build index
bwa-mem2 index reference.fa

# Align
bwa-mem2 mem -t 8 reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o aligned.bam -

# Index BAM
samtools index aligned.bam
```

### Post-alignment QC

```bash
# Alignment statistics
samtools flagstat aligned.bam

# Insert size distribution
samtools stats aligned.bam | grep "^IS"

# Coverage
samtools depth aligned.bam | awk '{sum+=$3} END {print "Mean coverage:", sum/NR}'
```

## Key Parameters

- STAR: `--outSAMtype BAM SortedByCoordinate`, `--twopassMode Basic`
- BWA-MEM2: `-t` threads, `-R` read group header
- Always include read groups (`@RG`) for GATK best practices
- Use `samtools view -b -q 30` to filter low-quality mappings

## Gotchas

- Build index with the exact reference FASTA and GTF you will quantify against
- For RNA-seq, always use splice-aware aligners (STAR, HISAT2), never BWA/Bowtie2
- chr prefix must be consistent between reference and annotation files
- For variant calling, mark duplicates with Picard/sambamba after alignment
- Multi-mapped reads (MAPQ=0) should be filtered for most downstream analyses