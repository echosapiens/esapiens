# Clinical Variant Interpretation

Interpret variant pathogenicity using ACMG/AMP guidelines and clinical databases.

## Recommended Tools

- **ClinVar**: curated variant clinical significance database
- **ACMG guidelines**: standards for variant classification
- **InterVar**: automated ACMG classification
- **REVEL**: ensemble pathogenicity scores
- **CADD**: combined annotation dependent depletion scores

## Common Workflows

### Query ClinVar via API

```python
import requests

def query_clinvar(gene_symbol, variant=None):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "clinvar", "term": f"{gene_symbol}[gene]"}
    if variant:
        params["term"] += f" AND {variant}"
    r = requests.get(base, params=params)
    return r.text
```

### ACMG Classification Criteria

The 28 ACMG criteria fall into:
- **Pathogenic (PVS1, PS1-5, PM1-6, PP1-5)**: loss-of-function, same AA change, hotspots
- **Benign (BA1, BS1-4, BP1-7)**: high allele frequency, benign computational evidence
- Classification requires combining criteria per ACMG rules

### InterVar: Automated ACMG Classification

```bash
intervar config --grch37  # or --grch38
intervar annotate -i input.vcf -o classified.vcf
```

## Key Parameters

- PVS1: null variant in gene where LOF is known mechanism
- BA1: allele frequency > 5% in gnomAD
- Always check for conflicting interpretations in ClinVar

## Gotchas

- ClinVar submissions may have conflicting interpretations; report review status
- ACMG criteria are guidelines; clinical context is essential
- VUS (Variant of Uncertain Significance) classification should not be treated as benign or pathogenic
- Population databases (gnomAD) allele frequency must match patient ancestry
- Always verify transcript annotations match the clinical laboratory's preferred transcript