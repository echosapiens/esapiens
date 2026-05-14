# Read Quality Control

Assess and improve sequencing read quality before alignment and analysis.

## Recommended Tools

- **FastQC**: comprehensive read quality reports
- **MultiQC**: aggregate multiple FastQC reports
- **fastp**: all-in-one QC, trimming, filtering with HTML reports
- **Trimmomatic**: flexible read trimming and adapter removal
- **Cutadapt**: adapter and quality trimming

## Common Workflows

### FastQC + MultiQC

```bash
# Run FastQC on all fastq files
fastqc -t 8 *.fastq.gz -o fastqc_out/

# Aggregate reports
multiqc fastqc_out/ -o multiqc_report/
```

### fastp (Recommended: Fast, All-in-One)

```bash
# QC + trimming + filtering in one step
fastp -i R1.fq.gz -I R2.fq.gz \
    -o R1.trimmed.fq.gz -O R2.trimmed.fq.gz \
    --detect_adapter_for_pe --trim_front1 5 --trim_front2 5 \
    --cut_mean_quality 20 --length_required 50 \
    --thread 8 --html fastp_report.html --json fastp.json
```

### Trimmomatic

```bash
trimmomatic PE -threads 8 \
    R1.fq.gz R2.fq.gz \
    R1_paired.fq.gz R1_unpaired.fq.gz \
    R2_paired.fq.gz R2_unpaired.fq.gz \
    ILLUMINACLIP:adapters.fa:2:30:10 \
    LEADING:3 TRAILING:3 SLIDINGWINDOW:4:20 MINLEN:50
```

### Python: Parse FastQC Report

```python
import json
with open("fastp.json") as f:
    report = json.load(f)

print(f"Before filtering: {report['summary']['before_filtering']['total_reads']} reads")
print(f"After filtering: {report['summary']['after_filtering']['total_reads']} reads")
print(f"Q30 rate: {report['summary']['after_filtering']['q30_rate']:.2%}")
```

## Key Parameters

- `--detect_adapter_for_pe`: auto-detect adapters in fastp
- `--cut_mean_quality 20`: mean quality threshold for sliding window
- `--length_required 50`: minimum read length after trimming
- Q30 > 80% is generally acceptable for RNA-seq
- Per-base sequence quality should be >20 across most positions

## Gotchas

- Always check adapter content; residual adapters cause alignment failures
- Over-represented sequences often indicate adapter contamination
- For RNA-seq, moderate 3' quality drop is normal due to poly-A tails
- fastp auto-detects adapters and produces paired HTML+JSON reports
- Duplicate rates > 50% in DNA-seq may indicate low complexity or PCR over-amplification