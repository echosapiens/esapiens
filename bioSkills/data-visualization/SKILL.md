# Data Visualization

Create publication-quality figures and interactive visualizations for biological data.

## Recommended Tools

- **matplotlib** + **seaborn**: standard scientific plotting
- **plotly**: interactive HTML visualizations
- **scanpy**: single-cell specific plots (UMAP, heatmap, dotplot)
- **pyGenomeTracks**: genome browser tracks
- **pycircos / Circos**: circular genome visualizations

## Common Workflows

### Publication-Quality Volcano Plot

```python
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

def volcano_plot(results, lfc_col="log2FoldChange", pval_col="padj",
                 lfc_thresh=1, pval_thresh=0.05, title="Volcano Plot"):
    results = results.copy()
    results["-log10(padj)"] = -np.log10(results[pval_col])

    # Classify
    results["significance"] = "Not significant"
    results.loc[(results[lfc_col] > lfc_thresh) & (results[pval_col] < pval_thresh), "significance"] = "Up"
    results.loc[(results[lfc_col] < -lfc_thresh) & (results[pval_col] < pval_thresh), "significance"] = "Down"

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = {"Not significant": "#B0B0B0", "Up": "#E64B35", "Down": "#4DBBD5"}
    for sig, group in results.groupby("significance"):
        ax.scatter(group[lfc_col], group["-log10(padj)"],
                   c=colors[sig], s=8 if sig == "Not significant" else 15,
                   alpha=0.5, label=sig, edgecolors="none")

    ax.axhline(-np.log10(pval_thresh), ls="--", c="gray", alpha=0.5)
    ax.axvline(-lfc_thresh, ls="--", c="gray", alpha=0.5)
    ax.axvline(lfc_thresh, ls="--", c="gray", alpha=0.5)
    ax.set_xlabel("log2 Fold Change", fontsize=12)
    ax.set_ylabel("-log10 adjusted p-value", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(fontsize=10)
    sns.despine()
    plt.tight_layout()
    plt.savefig("volcano.png", dpi=300, bbox_inches="tight")
```

### Heatmap with seaborn

```python
import seaborn as sns

# Centered, clustered heatmap
sns.clustermap(expression_matrix, cmap="RdBu_r", center=0,
               method="average", metric="euclidean",
               figsize=(12, 10), dendrogram_ratio=0.1,
               yticklabels=False, xticklabels=True)
plt.savefig("heatmap.png", dpi=300, bbox_inches="tight")
```

### Interactive Plotly Dashboard

```python
import plotly.express as px

fig = px.scatter(df, x="UMAP1", y="UMAP2", color="cell_type",
                 hover_data=["gene_symbol"], opacity=0.7,
                 title="Cell Types - UMAP")
fig.update_layout(template="plotly_white", font=dict(family="Helvetica"))
fig.write_html("umap_interactive.html")
```

## Key Parameters

- DPI: 300 minimum for publications; 600 for print
- Color palettes: use colorblind-friendly (viridis, cividis, cb-friendly)
- Figure size: 4-8 inches wide for single-column, 12-16 for two-column
- Font sizes: 8pt minimum axis labels, 6pt minimum tick labels

## Gotchas

- Always use vector formats (PDF, SVG) for publications when possible
- Avoid rainbow/jet colormaps; prefer viridis, RdBu, or cb-friendly palettes
- Heatmaps with unscaled data are misleading; always z-score or log-transform
- For large datasets (>10k points), use datashader or hexbin to avoid overplotting
- Seaborn defaults are publication-ready with minimal customization