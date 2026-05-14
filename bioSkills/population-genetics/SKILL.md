# Population Genetics

Analyze genetic variation across populations using allele frequencies, F-statistics, and selection scans.

## Recommended Tools

- **PLINK2**: genotype data management, association, LD pruning
- **vcftools**: VCF filtering and statistics
- **bcftools**: VCF manipulation
- **scikit-allel** (Python): array-based population genetics
- **ADMIXTURE**: ancestry decomposition
- **PCA**: via PLINK or scikit-allel

## Common Workflows

### PLINK: Basic Population Analysis

```bash
# Convert VCF to PLINK format
plink2 --vcf data.vcf.gz --make-pgen --out data

# LD pruning for PCA
plink2 --pfile data --indep-pairwise 50 5 0.2 --out pruned

# PCA
plink2 --pfile data --extract pruned.prune.in --pca 20 --out pca_results

# Association test
plink2 --pfile data --glm --covar covariates.txt --out assoc_results
```

### Python: scikit-allel F-statistics

```python
import allel
import numpy as np

# Load VCF
callset = allel.read_vcf("data.vcf.gz")
gt = allel.GenotypeArray(callset["calldata/GT"])

# Population assignment
pop1 = gt.take([0,1,2,3], axis=1)  # indices for pop1
pop2 = gt.take([4,5,6,7], axis=1)  # indices for pop2

# FST between populations
fst = allel.weir_cockerham_fst(pop1, pop2)
print(f"Mean FST: {np.nanmean(fst):.4f}")

# Nucleotide diversity (pi)
ac = gt.count_alleles()
pi = allel.sequence_diversity(ac, [0,1,2,3])
print(f"Nucleotide diversity: {pi:.6f}")
```

### ADMIXTURE: Ancestry Analysis

```bash
# LD prune first (required)
plink2 --vcf data.vcf.gz --indep-pairwise 50 5 0.2 --out prune
plink2 --vcf data.vcf.gz --extract prune.prune.in --make-bed --out data_pruned

# Run K=2 through K=10
for K in $(seq 2 10); do
    admixture data_pruned.bed $K
done

# Cross-validation error in *.log files; choose K with lowest CV
```

## Key Parameters

- FST > 0.15: moderate differentiation; > 0.25: high
- LD pruning r^2 threshold: 0.2 for PCA/admixture
- PCA: use at least 50k SNPs after LD pruning for stable results
- ADMIXTURE: K with lowest CV error is preferred

## Gotchas

- Always LD prune before PCA and ADMIXTURE
- FST estimates are sensitive to sample size imbalance
- Related individuals inflate FST; use KING or PLINK IBD to remove
- VCF must be filtered for Hardy-Weinberg equilibrium per population
- Different reference alleles across datasets cause allele flips