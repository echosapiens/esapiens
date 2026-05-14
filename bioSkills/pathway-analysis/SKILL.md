# Pathway Analysis

Perform functional enrichment and pathway analysis on gene lists using over-representation and gene set enrichment methods.

## Recommended Tools

- **g:Profiler**: web/API enrichment analysis across multiple databases
- **clusterProfiler** (R): comprehensive enrichment visualization
- **enrichr** (Python): Python client for Enrichr database
- **GSEA**: gene set enrichment analysis (pre-ranked)
- **ReactomePA**: Reactome pathway analysis

## Common Workflows

### clusterProfiler (R)

```r
library(clusterProfiler)
library(org.Hs.eg.db)

# Gene list (DEGs)
genes <- c("BRCA1", "TP53", "MYC", "EGFR", "PTEN", "CDH1", "RB1")

# Convert symbols to Entrez IDs
entrez <- bitr(genes, fromType="SYMBOL", toType="ENTREZID", OrgDb=org.Hs.eg.db)

# GO enrichment
go <- enrichGO(gene=entrez$ENTREZID, OrgDb=org.Hs.eg.db,
               ont="BP", pAdjustMethod="BH", pvalueCutoff=0.05, qvalueCutoff=0.2)

# KEGG pathway enrichment
kegg <- enrichKEGG(gene=entrez$ENTREZID, organism="hsa",
                   pAdjustMethod="BH", pvalueCutoff=0.05)

# Visualization
dotplot(go, showCategory=20)
cnetplot(go, showCategory=10)
```

### GSEA (Pre-ranked)

```r
# Pre-ranked gene list (sorted by log2FC or stat)
rnk <- read.table("genes.rnk", header=FALSE)
colnames(rnk) <- c("gene", "stat")

gsea <- GSEA(geneList=sort(rnk$stat, decreasing=TRUE),
             TERM2GENE=msigdb_hallmark,
             pvalueCutoff=0.05, pAdjustMethod="BH")

gseaplot2(gsea, geneSetID=1)
```

### Python: g:Profiler API

```python
from gprofiler import GProfiler

gp = GProfiler(return_dataframe=True)
results = gp.profile(
    organism="hsapiens",
    query=["BRCA1", "TP53", "MYC", "EGFR", "PTEN"],
    significance_threshold_method="fdr",
    no_evidences=False
)
print(results[["name", "p_value", "source"]].head(20))
```

## Key Parameters

- Multiple testing correction: Benjamini-Hochberg (FDR)
- Minimum gene set size: 5-10; maximum: 500
- GO terms: separate BP (biological process), MF (molecular function), CC (cellular component)
- KEGG organism codes: hsa (human), mmu (mouse), rno (rat)

## Gotchas

- Over-representation analysis is biased by input list composition
- GSEA uses the full ranked list and avoids arbitrary thresholds
- GO term redundancy: use simplify() in clusterProfiler or semantic similarity
- Always check organism code matches your data
- Pathway databases overlap; report source (GO, KEGG, Reactome, MSigDB)