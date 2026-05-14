# Variant Calling

Detecting genomic variants from sequencing data, including SNP, indel, and structural variant calling pipelines.

## Description

Variant calling identifies differences between a sample genome and a reference genome from aligned sequencing reads. This encompasses germline variant calling (diploid), somatic variant calling (tumor-normal pairs), and structural variant detection. The process involves pre-processing aligned reads, calling variants, filtering, and generating VCF output. Proper variant calling requires attention to sequencing platform artifacts, alignment quality, and statistical models.

## Recommended Tools

### Python Packages
- **pysam**: Python interface to samtools/htslib for BAM/VCF manipulation
- **cyvcf2**: Fast VCF parsing built on htslib
- **bcftools** (via subprocess): Variant calling and filtering
- **scikit-allel**: Population genetics and variant analysis
- **Hail**: Scalable variant analysis on large cohorts

### CLI Tools
- **GATK** (HaplotypeCaller, Mutect2): Industry standard for germline and somatic calling
- **bcftools mpileup/call**: Fast lightweight variant calling
- **FreeBayes**: Haplotype-based Bayesian variant detection
- **DeepVariant**: Neural network-based variant caller
- **Strelka2**: Fast somatic and germline variant calling
- **Manta**: Structural variant detection
- **Delly**: Structural variant calling with paired-end and split-read evidence
- **Lumpy**: SV detection integrating multiple signals
- **CNVkit**: Copy number variant detection from targeted sequencing

## Common Workflows

### Germline variant calling with GATK HaplotypeCaller

```bash
# Step 1: Call variants in GVCF mode (per sample)
gatk HaplotypeCaller \
    -R reference.fa \
    -I sample.bam \
    -O sample.g.vcf.gz \
    -ERC GVCF

# Step 2: Joint genotype multiple samples
gatk CombineGVCFs \
    -R reference.fa \
    --variant sample1.g.vcf.gz \
    --variant sample2.g.vcf.gz \
    -O cohort.g.vcf.gz

# Step 3: Genotype the combined GVCF
gatk GenotypeGVCFs \
    -R reference.fa \
    -V cohort.g.vcf.gz \
    -O cohort.vcf.gz

# Step 4: Hard filtering
gatk VariantFiltration \
    -V cohort.vcf.gz \
    --filter-expression "QD < 2.0" --filter-name "QD2" \
    --filter-expression "FS > 60.0" --filter-name "FS60" \
    --filter-expression "MQ < 40.0" --filter-name "MQ40" \
    -O cohort_filtered.vcf.gz
```

### Somatic variant calling with Mutect2

```bash
# Tumor-normal mode
gatk Mutect2 \
    -R reference.fa \
    -I tumor.bam -tumor TUMOR \
    -I normal.bam -normal NORMAL \
    -O somatic.vcf.gz

# Create panel of normals
gatk CreateSomaticPanelOfNormals \
    -vcfs normal1.vcf.gz \
    -vcfs normal2.vcf.gz \
    -O pon.vcf.gz

# Filter somatic calls
gatk FilterMutectCalls \
    -V somatic.vcf.gz \
    -R reference.fa \
    -O somatic_filtered.vcf.gz
```

### Variant calling with bcftools

```bash
# Call variants from BAM
bcftools mpileup -f reference.fa -b bamlist.txt -Ou | \
    bcftools call -mv -Oz -o variants.vcf.gz

# Index the output
bcftools index variants.vcf.gz

# Filter variants
bcftools filter -i 'QUAL>30 && DP>10' variants.vcf.gz -o filtered.vcf.gz
```

### Parse VCF with cyvcf2

```python
from cyvcf2 import VCF

vcf = VCF("variants.vcf.gz")
for variant in vcf:
    print(f"{variant.CHROM}:{variant.POS} {variant.REF}>{variant.ALT}")
    print(f"  QUAL: {variant.QUAL}")
    print(f"  DP: {variant.INFO.get('DP')}")
    # Genotypes per sample
    for sample, gt in zip(vcf.samples, variant.genotypes):
        allele1, allele2, phased = gt
        print(f"  {sample}: {allele1}/{allele2}")
vcf.close()
```

### Structural variant calling with Manta

```bash
# Configure and run Manta
configManta.py \
    --bam tumor.bam \
    --referenceFasta reference.fa \
    --runDir manta_run

manta_run/runWorkflow.py -m local -j 8

# Results in manta_run/results/variants/diploidSV.vcf.gz
```

## Key Parameters and Gotchas

### Germline Calling
- **GATK best practices**: Follow the full pipeline (MarkDuplicates, BaseRecalibration, HaplotypeCaller in GVCF mode, joint genotyping, VQSR). Skipping steps increases false positives.
- **VQSR vs hard filtering**: VQSR (Variant Quality Score Recalibration) requires >= 30 samples for reliable modeling. For small cohorts, use hard filtering with GATK-recommended thresholds.
- ** ploidy**: Set `-ploidy` correctly. HaplotypeCaller defaults to diploid. Use `-ploidy 1` for haploid organisms or chromosome X in males.

### Somatic Calling
- **Panel of normals**: Always create a PON from normal samples sequenced on the same platform to remove systematic artifacts.
- **Tumor purity**: Low tumor purity (<20%) reduces sensitivity. Consider using purity-adjusted tools like PureCN.
- **Matched normal**: A matched normal sample greatly reduces false positives. Tumor-only calling is possible but requires more aggressive filtering.

### Structural Variants
- **Read length**: Longer reads improve SV detection, especially for insertions. Short reads (<100 bp) miss many insertions.
- **Insert size**: Consistent library insert size is important for paired-end SV callers. Wide insert size distributions reduce sensitivity.
- **SV validation**: SV calls should be validated by orthogonal methods (long-read sequencing, PCR, optical mapping).

### Common Pitfalls
- **Reference bias**: Reads from the alternate allele may align poorly to the reference, causing under-calling. This is especially severe in regions of high divergence.
- **Strand bias**: Variants supported by reads from only one strand are likely artifacts. Check FS (Fisher's exact test for strand bias) in GATK output.
- **Low-complexity regions**: Homopolymer runs and microsatellites produce spurious indel calls. Filter these regions using mappability tracks.
- **Multiple alleles**: Multi-allelic sites (e.g., A>T, A>C) require special handling in downstream analysis. Use `bcftools norm` to split into biallelic records.
- **VCF normalization**: Always normalize VCFs with `bcftools norm -f reference.fa` to left-align indels and split multi-allelic sites.
