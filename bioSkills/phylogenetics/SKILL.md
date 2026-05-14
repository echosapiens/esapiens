# Phylogenetics

Build and analyze phylogenetic trees from sequence alignments.

## Recommended Tools

- **MAFFT**: multiple sequence alignment (accurate, scalable)
- **IQ-TREE2**: maximum likelihood tree inference with model selection
- **RAxML-NG**: fast ML tree inference, bootstrapping
- **FigTree / ete3**: tree visualization
- **biopython.Phylo**: tree parsing and manipulation in Python

## Common Workflows

### Full Phylogenetic Pipeline

```bash
# Align sequences
mafft --auto input_sequences.fasta > aligned.fasta

# Model selection + tree inference
iqtree2 -s aligned.fasta -m MFP -bb 1000 -nt AUTO

# Output: aligned.fasta.iqtree (tree + model info)
#         aligned.fasta.treefile (NEWICK tree)
#         aligned.fasta.ufboot (bootstrap trees)
```

### Python: Tree Manipulation with Biopython

```python
from Bio import Phylo
from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor

# Load tree
tree = Phylo.read("output.treefile", "newick")

# Render
Phylo.draw_ascii(tree)

# Get terminal branch names
terminals = tree.get_terminals()
print(f"Taxa: {len(terminals)}")
```

### Bootstrap + Consensus

```bash
# RAxML-NG with bootstrap
raxml-ng --all --msa aligned.fasta --model GTR+G --bs-trees 1000 --prefix output

# Consensus tree
raxml-ng --consensus --tree output.raxml.bootstraps --prefix consensus
```

## Key Parameters

- MAFFT: `--auto` for auto-strategy selection; `--maxiterate 1000` for iterative refinement
- IQ-TREE2: `-m MFP` for ModelFinder Plus; `-bb 1000` for ultrafast bootstrap
- Minimum 100 bootstrap replicates (1000 for publication)
- Use GTR+G as a reasonable default model if ModelFinder is too slow

## Gotchas

- Alignment quality determines tree quality; garbage in, garbage out
- Different alignment methods can produce different tree topologies
- Bootstrapping values < 70% indicate weak support for that node
- Root the tree using an outgroup, not midpoint rooting, when possible
- Remove poorly aligned regions with Gblocks or trimAl before tree inference