# Structural Biology: Structure I/O

Reading, writing, and parsing macromolecular structure files (PDB, mmCIF, MMTF).

## Description

Structure I/O covers the loading, saving, and programmatic access to 3D coordinate data of biological macromolecules. This includes PDB format (legacy), mmCIF/PDBx format (current standard), MMTF (binary compressed), and related file types. Understanding format differences is critical for downstream structural analysis.

## Recommended Tools

### Python Packages
- **BioPython** (`Bio.PDB`): Full-featured PDB/mmCIF parser with structure object model
- **MDAnalysis**: Efficient I/O for large trajectories and structure ensembles
- **MDTraj**: Lightweight, fast structure I/O with NumPy integration
- **pytraj** (AmberTools): CPPTRAJ Python interface for structure manipulation
- **gemmi**: Modern mmCIF/PDB parser, fast and memory-efficient
- **pdbfixer**: Structure repair and preparation

### CLI Tools
- **grepawk** on PDB files for quick inspection
- **pdb-tools** (`pdb_tidy`, `pdb_selchain`, `pdb_reres`): Swiss-army-knife PDB manipulation
- **cif2pdb / pdb2cif**: Format conversion
- **MMTF Python/Java decoders**: High-performance binary format reading

### Databases
- RCSB PDB (rcsb.org): HTTP API and batch download
- PDBe (pdbe.org): REST API with advanced queries
- AlphaFold DB (alphafold.ebi.ac.uk): Predicted structure downloads

## Common Workflows

### Load a PDB file with BioPython

```python
from Bio.PDB import PDBParser

parser = PDBParser(QUIET=True)
structure = parser.get_structure("1abc", "1abc.pdb")

for model in structure:
    for chain in model:
        print(f"Chain {chain.id}: {len(list(chain.get_residues()))} residues")
        for residue in chain:
            if residue.id[0] == " ":  # Skip heteroatoms/water
                ca = residue["CA"]
                print(f"  {residue.resname} CA at {ca.coord}")
```

### Load an mmCIF file with gemmi

```python
import gemmi

doc = gemmi.cif.read("1abc.cif")
block = doc[0]
st = gemmi.make_structure_from_block(block)

for model in st:
    for chain in model:
        print(f"Chain {chain.name}: {chain.length} residues")
```

### Download a structure from RCSB PDB

```python
import requests
from pathlib import Path

def download_pdb(pdb_id: str, output_dir: str = ".") -> Path:
    """Download a PDB file in mmCIF format from RCSB."""
    pdb_id = pdb_id.lower()
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    out = Path(output_dir) / f"{pdb_id}.cif"
    out.write_text(resp.text)
    return out

def download_pdb_batch(pdb_ids: list[str], output_dir: str = ".") -> list[Path]:
    """Batch download multiple structures."""
    paths = []
    for pid in pdb_ids:
        try:
            paths.append(download_pdb(pid, output_dir))
        except requests.HTTPError as e:
            print(f"Failed to download {pid}: {e}")
    return paths
```

### Query the RCSB PDB REST API

```python
import requests

def search_pdb_by_organism(organism: str) -> list[str]:
    """Search RCSB for structures from a given organism."""
    query = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_entry_info.organism_names",
                "operator": "exact_match",
                "value": organism,
            },
        },
        "return_type": "entry",
        "request_options": {"return_all_hits": True},
    }
    resp = requests.post(
        "https://search.rcsb.org/rcsbsearch/v2/query",
        json=query,
        timeout=60,
    )
    resp.raise_for_status()
    return [hit["identifier"] for hit in resp.json().get("result_set", [])]
```

### Extract specific chains from a structure

```python
from Bio.PDB import PDBParser, PDBIO, Select

class ChainSelect(Select):
    def __init__(self, chain_ids: list[str]):
        self.chain_ids = chain_ids

    def accept_chain(self, chain):
        return chain.id in self.chain_ids

parser = PDBParser(QUIET=True)
structure = parser.get_structure("1abc", "1abc.pdb")

io = PDBIO()
io.set_structure(structure)
io.save("1abc_chainA.pdb", ChainSelect(["A"]))
```

### Write a structure to mmCIF with gemmi

```python
import gemmi

st = gemmi.read_structure("input.pdb")
# ... modifications ...
st.make_mmcif_document().write_file("output.cif")
```

## Key Parameters and Gotchas

### Format Differences
- **PDB format** has a hard limit of 99999 atoms and 62 chains (single-character IDs). Large structures require mmCIF.
- **mmCIF** uses three-character chain labels (`auth_asym_id` vs `label_asym_id`). The `auth_asym_id` matches the legacy PDB chain ID; `label_asym_id` is the canonical mmCIF identifier and may differ.
- **MMTF** is the most compact format but lacks some annotation fields present in mmCIF.

### Common Pitfalls
- **Hetero flags**: In BioPython, `residue.id` is a tuple `(het_flag, seq_num, icode)`. Heteroatoms have a non-blank het_flag (e.g., `("W", 1, " ")` for water). Always check `residue.id[0] == " "` to filter standard residues.
- **Insertion codes**: Residues with insertion codes (e.g., 1A, 1B) share the same sequence number but differ in icode. Sort by `(seq_num, icode)` for correct ordering.
- **Alternate locations**: Atoms may have alternate conformations (`altloc`). BioPython returns the first by default; use `atom.altloc` to check.
- **Multiple models**: NMR structures contain multiple models. Always specify which model you want or iterate explicitly.
- **Numbering gaps**: PDB residue numbering does not always correspond to UniProt sequence positions. Use SIFTS mapping for cross-referencing.
- **Biological assemblies**: The asymmetric unit may differ from the biological assembly. Check `REMARK 350` (PDB) or `_pdbx_struct_assembly` (mmCIF) for assembly information.
- **Download rate limits**: RCSB PDB requests should be throttled to avoid rate-limiting (roughly 10 requests/second for batch downloads).

### Performance Tips
- Use `gemmi` for large structures (>100k atoms) -- it is 10-50x faster than BioPython for parsing.
- For trajectory I/O (MD simulations), prefer `MDTraj` or `MDAnalysis` over `Bio.PDB`.
- Use MMTF format when downloading large batches -- files are ~5-10x smaller than mmCIF.
