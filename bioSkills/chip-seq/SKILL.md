# ChIP-seq Analysis

Identify protein-DNA binding sites from chromatin immunoprecipitation sequencing data.

## Recommended Tools

- **BWA-MEM2 / Bowtie2**: read alignment
- **MACS2**: peak calling (gold standard)
- **sambamba**: fast BAM processing, duplicate marking
- **deepTools**: QC, heatmaps, metagene profiles
- **HOMER**: motif discovery and annotation

## Common Workflows

### Full ChIP-seq Pipeline

```bash
# Align
bwa-mem2 mem -t 8 reference.fa chip_R1.fq.gz | \
    samtools sort -o chip.bam -
samtools index chip.bam

# Filter and remove duplicates
sambamba view -t 8 -f bam -F "mapping_quality>=30 && paired" chip.bam | \
    sambamba markdup -t 8 --remove-duplicates /dev/stdin chip filtered.bam

# Call peaks
macs2 callpeak -t chip_filtered.bam -c input_filtered.bam \
    -f BAMPE -g hs --outdir macs2_out/ -n sample \
    --broad --broad-cutoff 0.1
```

### QC with deepTools

```bash
# FRiP (Fraction of Reads in Peaks)
echo "FRiP: $(samtools view -c chip_filtered.bam) total," \
     "$(bedtools intersect -a chip_filtered.bam -b macs2_out/sample_peaks.broadPeak -ubam | samtools view -c -) in peaks"

# Metagene profile
computeMatrix reference-point -S chip_filtered.bam -R macs2_out/sample_peaks.broadPeak \
    --referencePoint center -b 2000 -a 2000 -out matrix.gz
plotProfile -m matrix.gz -out profile.png
```

### Motif Discovery

```bash
findMotifsGenome.pl macs2_out/sample_peaks.broadPeak hg38 homer_out/ -size 200
```

## Key Parameters

- Always use matched input control for peak calling
- `--broad`: histone marks (H3K27me3, H3K36me3); narrow: transcription factors
- `--broad-cutoff 0.1`: FDR for broad peaks
- `-q 0.01`: FDR threshold for narrow peaks
- FRiP > 1% is acceptable; > 5% is good for TFs

## Gotchas

- Do NOT skip the input control; this causes massive false positive rates
- Duplicate removal is essential for ChIP-seq (not for ATAC-seq)
- Different histone marks require narrow vs broad peak settings
- Blacklist regions (ENCODE) must be removed before downstream analysis
- Cross-correlation (NSC/RSC) from phantom peak is a key QC metric