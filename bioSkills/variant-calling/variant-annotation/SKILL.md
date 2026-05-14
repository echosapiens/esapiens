# Variant Annotation

Annotate genetic variants with functional consequences, population frequencies, and clinical significance.

## Recommended Tools

- **VEP** (Ensembl Variant Effect Predictor): industry standard for functional annotation
- **SnpEff**: fast variant annotation and effect prediction
- **ANNOVAR**: comprehensive annotation with multiple databases
- **bcftools csq**: built-in consequence annotation for VCF

## Common Workflows

### Annotate VCF with SnpEff

```bash
# Download required database
java -jar snpEff.jar download GRCh38.105

# Annotate VCF
java -jar snpEff.jar -v GRCh38.105 input.vcf > annotated.vcf
```

### VEP Annotation

```bash
# Install and cache
vep --install --assembly GRCh38

# Annotate VCF
vep -i input.vcf -o annotated.vcf --vcf --everything --assembly GRCh38
```

### Python: Annotate with PyVCF

```python
import vcf

reader = vcf.Reader(open("input.vcf", "r"))
for record in reader:
    for alt in record.ALT:
        print(f"{record.CHROM}:{record.POS} {record.REF}>{alt}")
        print(f"  Quality: {record.QUAL}")
        print(f"  Filter: {record.FILTER}")
        for sample in record.samples:
            if sample["GT"] != "./.":
                print(f"  {sample.sample}: {sample['GT']}")
```

## Key Parameters

- `--everything`: enable all VEP annotations
- `--pick`: select one consequence per variant (canonical transcript)
- `--af`: include allele frequencies from gnomAD, 1000G
- `--sift b --polyphen b`: pathogenicity predictions
- `--cache --offline`: use local cache for speed

## Gotchas

- Always verify assembly version matches your reference (GRCh37 vs GRCh38)
- SnpEff databases must match the VCF reference build
- VEP cache files are large; allow sufficient disk space
- Multiple transcripts per variant mean multiple annotations; use `--pick` for one per variant
- chr prefix inconsistency (chr1 vs 1) causes annotation failures