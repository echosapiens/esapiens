# Single-Cell RNA-seq Analysis

Process and analyze single-cell RNA sequencing data using scanpy and related tools.

## Recommended Tools

- **Scanpy** (Python): comprehensive scRNA-seq analysis
- **Seurat** (R): popular scRNA-seq framework
- **CellRanger** (10x Genomics): alignment and counting for 10x data
- **scvi-tools**: deep generative models (VAE-based)
- **Harmony / scVI**: batch correction methods

## Common Workflows

### Scanpy Standard Pipeline

```python
import scanpy as sc

# Load 10x data
adata = sc.read_10x_mtx("filtered_feature_bc_matrix/")

# Basic filtering
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)

# Calculate QC metrics
adata.var["mt"] = adata.var_names.str.startswith("MT-")
sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)

# Filter: n_genes 200-5000, MT% < 20
adata = adata[adata.obs.n_genes_by_counts < 5000, :]
adata = adata[adata.obs.pct_counts_mt < 20, :]

# Normalize, log-transform, find variable genes
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=2000, flavor="seurat_v3")

# Scale, PCA, neighbors, UMAP
sc.pp.scale(adata, max_value=10)
sc.tl.pca(adata, n_comps=50)
sc.pp.neighbors(adata, n_pcs=30)
sc.tl.umap(adata)

# Cluster
sc.tl.leiden(adata, resolution=0.5)

# Marker genes
sc.tl.rank_genes_groups(adata, "leiden", method="wilcoxon")
sc.pl.rank_genes_groups(adata, n_genes=10, sharey=False)
```

### Cell Type Annotation

```python
# Manual annotation with known markers
marker_genes = {
    "T cells": ["CD3D", "CD3E", "CD3G"],
    "B cells": ["MS4A1", "CD79A", "CD79B"],
    "Monocytes": ["LYZ", "CD14", "FCGR3A"],
    "NK cells": ["NCAM1", "NKG7", "GNLY"],
}
sc.pl.dotplot(adata, marker_genes, groupby="leiden")
```

## Key Parameters

- Min genes per cell: 200; max: 5000 (adjust for tissue)
- MT% threshold: < 20% for most tissues; < 5% for high-quality
- n_top_genes: 2000-5000 for variable gene selection
- Leiden resolution: 0.3-1.0 (higher = more clusters)
- n_pcs: 30 is standard; check elbow plot for optimal

## Gotchas

- Always use raw counts as input, not normalized data
- Batch correction should be applied before clustering, after PCA
- Doublets inflate apparent cell types; use Scrublet or DoubletFinder
- Ambient RNA (soup) can cause false marker expression; considerSoupX or CellBender
- Seurat v5 and scanpy use different default normalization; results may differ