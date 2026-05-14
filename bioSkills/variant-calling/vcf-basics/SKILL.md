# Variant Calling: VCF Basics

Understanding, parsing, and manipulating Variant Call Format (VCF) files.

## Description

The Variant Call Format (VCF) is the standard file format for representing genomic variants including SNPs, indels, and structural variants. VCF files consist of a header section with metadata and a data section with fixed columns (CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO) plus variable sample-level genotype columns. Proficiency with VCF is essential for any variant analysis pipeline.

## Recommended Tools

### Python Packages
- **cyvcf2**: Fast VCF parsing built on htslib C library
- **pysam** (`pysam.VariantFile`): Full-featured VCF reading/writing with htslib
- **scikit-allel**: VCF reading and population genetics analysis
- **Hail**: Distributed VCF processing for large cohorts

### CLI Tools
- **bcftools**: The primary toolkit for VCF manipulation, filtering, and analysis
- **vcftools**: Legacy VCF analysis toolkit (being superseded by bcftools)
- **bedtools intersect**: Intersect VCF with BED regions
- **gatk**: VCF filtering, annotation, and manipulation

## Common Workflows

### Parse a VCF file with cyvcf2

```python
from cyvcf2 import VCF

vcf = VCF("variants.vcf.gz")

# Access header information
for sample in vcf.samples:
    print(f"Sample: {sample}")

for variant in vcf:
    chrom = variant.CHROM
    pos = variant.POS
    ref = variant.REF
    alts = variant.ALT
    qual = variant.QUAL
    filt = variant.FILTER

    # INFO field access
    dp = variant.INFO.get("DP")
    af = variant.INFO.get("AF")

    # Genotypes: list of [allele1, allele2, phased]
    for sample, gt in zip(vcf.samples, variant.genotypes):
        a1, a2, phased = gt
        gt_str = f"{a1}|{a2}" if phased else f"{a1}/{a2}"
        print(f"  {sample}: {gt_str}")

vcf.close()
```

### Read and write VCF with pysam

```python
import pysam

# Read VCF
vcf_in = pysam.VariantFile("input.vcf.gz")

# Print header
print(vcf_in.header)

# Write filtered VCF
vcf_out = pysam.VariantFile("filtered.vcf", "w", header=vcf_in.header)

for record in vcf_in:
    if record.qual and record.qual >= 30:
        dp = record.info.get("DP", 0)
        if dp >= 10:
            vcf_out.write(record)

vcf_in.close()
vcf_out.close()
```

### Common bcftools operations

```bash
# View VCF header
bcftools view -h variants.vcf.gz

# Filter by quality and depth
bcftools view -i 'QUAL>30 && DP>10' variants.vcf.gz -o filtered.vcf.gz -Oz

# Extract specific regions
bcftools view -r chr1:1000000-2000000 variants.vcf.gz -o region.vcf.gz -Oz

# Select specific samples
bcftools view -s SAMPLE1,SAMPLE2 cohort.vcf.gz -o subset.vcf.gz -Oz

# Count variants per sample
bcftools stats cohort.vcf.gz > stats.txt

# Merge multiple VCFs
bcftools merge sample1.vcf.gz sample2.vcf.gz -o merged.vcf.gz -Oz

# Normalize (left-align indels, split multi-allelic)
bcftools norm -f reference.fa -m -both variants.vcf.gz -o normalized.vcf.gz -Oz

# Compare two VCFs
bcftools isec -p output_dir/ -n=2 a.vcf.gz b.vcf.gz

# Annotate with ID from dbSNP
bcftools annotate -a dbsnp.vcf.gz -c ID variants.vcf.gz -o annotated.vcf.gz -Oz
```

### Extract variant statistics

```python
from cyvcf2 import VCF
from collections import Counter

vcf = VCF("variants.vcf.gz")

type_counts = Counter()
qual_values = []

for variant in vcf:
    # Classify variant type
    if variant.is_snp:
        type_counts["SNP"] += 1
    elif variant.is_indel:
        type_counts["INDEL"] += 1
    elif variant.is_sv:
        type_counts["SV"] += 1
    else:
        type_counts["OTHER"] += 1

    if variant.QUAL is not None:
        qual_values.append(variant.QUAL)

print("Variant type counts:")
for vtype, count in type_counts.items():
    print(f"  {vtype}: {count}")

import numpy as np
print(f"QUAL: median={np.median(qual_values):.1f}, mean={np.mean(qual_values):.1f}")

vcf.close()
```

### Convert VCF to a pandas DataFrame

```python
from cyvcf2 import VCF
import pandas as pd

def vcf_to_dataframe(vcf_path: str) -> pd.DataFrame:
    """Convert VCF to DataFrame with standard columns."""
    vcf = VCF(vcf_path)
    records = []
    for var in vcf:
        records.append({
            "CHROM": var.CHROM,
            "POS": var.POS,
            "ID": var.ID,
            "REF": var.REF,
            "ALT": ",".join(var.ALT),
            "QUAL": var.QUAL,
            "FILTER": var.FILTER,
            "DP": var.INFO.get("DP"),
            "AF": var.INFO.get("AF"),
            "is_snp": var.is_snp,
            "is_indel": var.is_indel,
        })
    vcf.close()
    return pd.DataFrame(records)

df = vcf_to_dataframe("variants.vcf.gz")
print(df.head())
print(df.describe())
```

## Key Parameters and Gotchas

### VCF Structure
- **CHROM and POS**: 1-based coordinate system. POS is the position of the first base in REF.
- **ID**: Semi-colon separated list of identifiers (e.g., rs numbers from dbSNP). Missing values are represented by `.`.
- **REF**: Reference allele on the forward strand. Must be one of A, C, G, T, N (with IUPAC ambiguity).
- **ALT**: Comma-separated list of alternate alleles. `.` means no variant. `*` represents a spanning deletion.
- **QUAL**: Phred-scaled quality score. QUAL=30 means 1/1000 probability the call is wrong.
- **FILTER**: `PASS` means all filters passed. `.` means no filters applied. Multiple filters are semicolon-separated.

### Genotype Fields
- **GT**: Genotype, encoded as allele indices separated by `/` (unphased) or `|` (phased). `0/0` = homozygous reference, `0/1` = heterozygous, `1/1` = homozygous alternate.
- **AD**: Allelic depths for ref and alt alleles (comma-separated).
- **DP**: Read depth at this position for this sample.
- **GQ**: Genotype quality, Phred-scaled.
- **PL**: Phred-scaled likelihoods for each possible genotype.

### Common Pitfalls
- **Multi-allelic sites**: Sites with multiple ALT alleles (e.g., `REF=A ALT=T,C`) require normalization with `bcftools norm -m -` before many downstream analyses.
- **Left-alignment**: Indels should be left-aligned to be comparable across callers. Use `bcftools norm -f reference.fa`.
- **VCF vs BCF**: BCF is the binary equivalent of VCF. Always use compressed VCF (`.vcf.gz`) with tabix index for efficient random access.
- **Missing data**: `.` in GT fields means no call. Different tools handle missing genotypes differently; check documentation.
- **Zero-based vs one-based**: VCF uses 1-based coordinates. Python/pysam uses 0-based internally but converts automatically. BedTools uses 0-based half-open.
- **Memory**: Loading a large VCF into memory as a DataFrame is impractical for whole-genome data. Stream with cyvcf2 or use Hail for cohort-scale analysis.
