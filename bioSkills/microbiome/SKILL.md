# Microbiome Analysis

Analyze 16S rRNA amplicon sequencing data for microbial community profiling.

## Recommended Tools

- **QIIME2**: end-to-end microbiome analysis pipeline
- **DADA2** (R): amplicon sequence variant (ASV) inference
- **phyloseq** (R): diversity, ordination, differential abundance
- **DESeq2**: differential abundance of ASVs
- **ANCOM-BC**: compositionally-aware differential abundance

## Common Workflows

### DADA2 Pipeline (R)

```r
library(dada2)

# List files
fnFs <- sort(list.files("data", pattern="_R1.fastq.gz", full.names=TRUE))
fnRs <- sort(list.files("data", pattern="_R2.fastq.gz", full.names=TRUE))

# Filter and trim
filtFs <- file.path("filtered", basename(fnFs))
filtRs <- file.path("filtered", basename(fnRs))
filterAndTrim(fnFs, filtFs, fnRs, filtRs, truncLen=c(240,200),
              maxN=0, maxEE=c(2,2), truncQ=2, rm.phix=TRUE, compress=TRUE)

# Learn errors, dereplicate, denoise
errF <- learnErrors(filtFs, multithread=TRUE)
errR <- learnErrors(filtRs, multithread=TRUE)
derepFs <- derepFastq(filtFs); derepRs <- derepFastq(filtRs)
dadaFs <- dada(derepFs, err=errF, multithread=TRUE)
dadaRs <- dada(derepRs, err=errR, multithread=TRUE)

# Merge, remove chimeras, assign taxonomy
mergers <- mergePairs(dadaFs, derepFs, dadaRs, derepRs)
seqtab <- makeSequenceTable(mergers)
seqtab_nochim <- removeBimeraDenovo(seqtab, method="consensus", multithread=TRUE)
taxa <- assignTaxonomy(seqtab_nochim, "silva_nr_v138_train_set.fa.gz", multithread=TRUE)
```

### Diversity Analysis with phyloseq

```r
library(phyloseq)

ps <- phyloseq(otu_table(seqtab_nochim, taxa_are_rows=FALSE),
               sample_data(metadata),
               tax_table(taxa))

# Alpha diversity
plot_richness(ps, x="group", measures=c("Shannon","Simpson","Observed"))

# Beta diversity (PCoA)
ord <- ordinate(ps, method="PCoA", distance="bray")
plot_ordination(ps, ord, color="group") + stat_ellipse()

# PERMANOVA test
library(vegan)
dist_mat <- phyloseq::distance(ps, method="bray")
adonis2(dist_mat ~ group, data=metadata)
```

## Key Parameters

- truncLen should match where quality drops (check FastQC first)
- maxEE=2 allows 2 expected errors per read
- Silva or Greengenes for 16S taxonomy; UNITE for ITS
- Minimum 10,000 reads per sample for reliable diversity estimates

## Gotchas

- ASVs (DADA2) are preferred over OTUs (QIIME1) — single-nucleotide resolution
- Compositional data: do not use raw counts for differential abundance; use ANCOM-BC or ALDEx2
- Rarefaction removes data; prefer variance-stabilizing transforms
- Negative controls are essential for detecting contamination
- 16S cannot resolve below genus level reliably; use shotgun metagenomics for species-level