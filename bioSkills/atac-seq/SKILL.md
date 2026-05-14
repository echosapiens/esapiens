# ATAC-seq Analysis

Analyze Assay for Transposase-Accessible Chromatin sequencing data to map open chromatin regions.

## Recommended Tools

- **BWA-MEM2**: read alignment
- **MACS2**: peak calling with shifted model
- **Genrich**: ATAC-seq-specific peak caller
- **deepTools**: QC, TSS enrichment, heatmaps
- **chromVAR**: variation in chromatin accessibility across cells/conditions
- **TOBIAS**: transcription factor footprinting

## Common Workflows

### Full ATAC-seq Pipeline

```bash
# Align (do NOT remove duplicates for ATAC-seq)
bwa-mem2 mem -t 8 reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o aligned.bam -

# Filter: remove mitochondrial, low-MAPQ, unmapped
samtools view -h aligned.bam | \
    grep -v "chrM" | \
    samtools view -b -q 30 -F 0x904 - > filtered.bam

# Shift reads (+4/-5 bp for Tn5 offset)
alignmentSieve --bam filtered.bam -p 8 --ATACshift --shiftSizes 4 -5 -o shifted.bam

# Call peaks
macs2 callpeak -t shifted.bam -f BAMPE -g hs \
    --outdir macs2_out/ -n sample --keep-dup all -q 0.01
```

### TSS Enrichment Score

```python
import pyBigWig
import numpy as np

# Compute TSS enrichment from pileup at TSS vs flanking regions
bw = pyBigWig.open("atac.bw")
tss_signal = bw.stats("chr1", 1000000-1000, 1000000+1000, type="mean")
flank_signal = bw.stats("chr1", 1000000-2000, 1000000-1000, type="mean")
enrichment = np.mean(tss_signal) / np.mean(flank_signal)
print(f"TSS enrichment: {enrichment:.1f}")
```

### Footprinting with TOBIAS

```bash
TOBIAS ATACorrect --bam shifted.bam --genome genome.fa --regions peaks.bed --outdir corrected/
TOBIAS FootprintScores --signal corrected/atac_corrected.bw --regions peaks.bed --output footprints.bw
TOBIAS BINDetect --motifs motifs.pfm --footprints footprints.bw --genome genome.fa --regions peaks.bed --outdir binding/
```

## Key Parameters

- Do NOT remove duplicates (Tn5 transposition creates apparent duplicates)
- Shift reads +4/-5 bp to correct for Tn5 insertion offset
- `--keep-dup all` in MACS2 for ATAC-seq
- TSS enrichment > 6 is good; > 10 is excellent
- Filter mitochondrial reads (can be 20-50% of total reads)

## Gotchas

- Mitochondrial reads dominate ATAC-seq; always filter chrM first
- Nucleosome-free fragment (< 100 bp) represents open chromatin
- Mono-nucleosome (180-247 bp) and di-nucleosome fragments have different biological meaning
- Do not apply duplicate removal — it destroys true biological signal
- Blacklist regions must be removed (ENCODE blacklist for your genome)