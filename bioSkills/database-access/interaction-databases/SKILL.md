# Protein-Protein Interaction Databases

Query and analyze protein-protein interaction networks from curated databases.

## Recommended Tools

- **STRING API**: comprehensive PPI network with confidence scores
- **BioGRID**: curated biological interaction database
- **NetworkX** (Python): graph analysis and visualization
- **PySTRING**: Python client for STRING database
- **igraph**: fast network analysis for large graphs

## Common Workflows

### STRING API

```python
import requests

# Get interaction partners
def get_string_interactions(protein_id, species=9606):
    url = "https://string-db.org/api/json/interaction_partners"
    params = {
        "identifiers": protein_id,
        "species": species,
        "required_score": 700,  # confidence threshold 0-1000
        "network_flavor": "confidence"
    }
    r = requests.get(url, params=params)
    return r.json()

# Example: BRCA1 interactors
partners = get_string_interactions("BRCA1")
for p in partners[:10]:
    print(f"{p['preferredName_B']}: score={p['score']}")
```

### Network Analysis with NetworkX

```python
import networkx as nx
import matplotlib.pyplot as plt

# Build network from STRING output
G = nx.Graph()
for interaction in partners:
    G.add_edge(
        interaction["preferredName_A"],
        interaction["preferredName_B"],
        weight=interaction["score"]
    )

# Network statistics
print(f"Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
print(f"Degree centrality: {nx.degree_centrality(G)}")

# Find hubs
hubs = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:5]

# Visualize
pos = nx.spring_layout(G, k=1)
nx.draw(G, pos, node_size=300, font_size=8, with_labels=True)
plt.savefig("ppi_network.png", dpi=300)
```

### BioGRID API

```python
import requests

# Query interactions for a gene
r = requests.get("https://webservice.thebiogrid.org/interactions/",
    params={
        "geneList": "BRCA1",
        "taxId": 9606,
        "format": "json",
        "accesskey": "YOUR_KEY"
    })
interactions = r.json()
```

## Key Parameters

- STRING confidence score: 400 (low), 700 (high), 900 (highest)
- Use `required_score` to filter low-confidence interactions
- species: 9606 (human), 10090 (mouse), 4932 (yeast)
- For network analysis, filter by `combined_score > 0.7` for reliability

## Gotchas

- STRING includes predicted interactions; check experimental vs computational evidence
- BioGRID is manually curated but smaller than STRING
- For publication, cite both the database version and accession
- Large networks (>500 nodes) become visually unreadable; use module detection first
- PPI networks are undirected; use directed edges only when supported by evidence