# Structural Biology: AlphaFold Predictions

Working with AlphaFold and related structure prediction tools, including running predictions, parsing confidence metrics, and integrating predictions into structural analysis pipelines.

## Description

AlphaFold2 and its successors (AlphaFold-Multimer, AlphaFold3, ESMFold, RoseTTAFold) produce predicted protein structures with per-residue confidence scores (pLDDT and PAE). This skill covers running predictions locally or via APIs, interpreting output formats, filtering low-confidence regions, and using predictions for downstream analysis such as docking, interface prediction, and experimental design.

## Recommended Tools

### Python Packages
- **colabfold/alphafold**: ColabFold for accessible AlphaFold2 predictions
- **alphafold3**: AlphaFold3 for protein-ligand-nucleic acid complexes
- **biopython** (`Bio.PDB`): Parsing predicted PDB/mmCIF files
- **gemmi**: Fast parsing of AlphaFold mmCIF output with confidence annotations
- **py3Dmol**: Interactive visualization of predictions in Jupyter
- **esm** (Facebook ESM): ESMFold end-to-end structure prediction
- **OpenFold**: Open-source AlphaFold2 reimplementation

### CLI Tools
- **colabfold_batch**: Batch ColabFold predictions on local GPU
- **alphafold**: Official DeepMind AlphaFold2 pipeline
- **esm-fold**: ESMFold command-line prediction
- **foldseek**: Fast structural alignment of predicted structures

### Databases
- **AlphaFold DB** (alphafold.ebi.ac.uk): Pre-computed predictions for 200M+ proteins
- **ESMet** (esmatlas.com): ESMFold predictions for metagenomic proteins

## Common Workflows

### Download a prediction from AlphaFold DB

```python
import requests
from pathlib import Path

def download_alphafold(uniprot_id: str, output_dir: str = ".") -> Path:
    """Download AlphaFold prediction from EBI."""
    url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.cif"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    out = Path(output_dir) / f"AF-{uniprot_id}.cif"
    out.write_text(resp.text)
    return out

def download_alphafold_pae(uniprot_id: str, output_dir: str = ".") -> Path:
    """Download PAE (Predicted Aligned Error) data."""
    url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-predicted_aligned_error_v4.json"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    out = Path(output_dir) / f"AF-{uniprot_id}_pae.json"
    out.write_text(resp.text)
    return out
```

### Parse pLDDT scores from a predicted structure

```python
import gemmi
import numpy as np

def extract_plddt(cif_path: str) -> np.ndarray:
    """Extract per-residue pLDDT scores from AlphaFold mmCIF."""
    doc = gemmi.cif.read(cif_path)
    block = doc[0]
    # pLDDT is stored in the B-factor column
    cat = block.find("_atom_site.")
    b_factors = []
    for row in cat:
        if row[17] == "CA":  # CA atoms only for per-residue summary
            b_factors.append(float(row[20]))  # B-factor column = pLDDT
    return np.array(b_factors)

def confidence_filter(plddt: np.ndarray, threshold: float = 70.0) -> np.ndarray:
    """Return boolean mask for residues above pLDDT threshold."""
    return plddt >= threshold

plddt = extract_plddt("AF-P12345.cif")
print(f"Mean pLDDT: {plddt.mean():.1f}")
print(f"Residues > 70: {confidence_filter(plddt).sum()} / {len(plddt)}")
```

### Parse and visualize PAE matrix

```python
import json
import numpy as np
import matplotlib.pyplot as plt

def plot_pae(pae_json_path: str):
    """Plot the Predicted Aligned Error matrix."""
    with open(pae_json_path) as f:
        data = json.load(f)
    pae = np.array(data[0]["predicted_aligned_error"])

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pae, cmap="bwr", vmin=0, vmax=pae.max())
    ax.set_xlabel("Residue index (aligned)")
    ax.set_ylabel("Residue index (scored)")
    ax.set_title("Predicted Aligned Error")
    plt.colorbar(im, ax=ax, label="PAE (Angstrom)")
    plt.tight_layout()
    plt.savefig("pae_plot.png", dpi=150)
    plt.close()
```

### Run ESMFold prediction locally

```python
import esm

model = esm.pretrained.esmfold_v1()
model = model.eval().cuda()

sequence = "MKWVTFISLLFLFSSAYSRGVFRRDAHKSELAH"
with torch.no_grad():
    output = model.infer(sequence)

# Output contains coordinates and pLDDT
coords = output["positions"]  # (L, 37, 3) atom37 format
plddt = output["plddt"]      # (L,) per-residue confidence
```

### Run ColabFold batch predictions

```bash
# Prepare input: CSV with 'id,sequence' columns
colabfold_batch input.csv output_dir/ \
    --templates \
    --use-gpu \
    --model-type alphafold2_ptm \
    --num-recycles 3 \
    --max-seqs 1024
```

### Filter low-confidence regions before downstream analysis

```python
from Bio.PDB import PDBParser, PDBIO, Select

class ConfidenceSelect(Select):
    """Select residues with pLDDT above threshold."""

    def __init__(self, plddt_dict: dict, threshold: float = 70.0):
        self.plddt_dict = plddt_dict  # {(chain, resseq): plddt}
        self.threshold = threshold

    def accept_residue(self, residue):
        key = (residue.parent.id, residue.id[1])
        if key in self.plddt_dict:
            return self.plddt_dict[key] >= self.threshold
        return False  # Skip residues without pLDDT

parser = PDBParser(QUIET=True)
structure = parser.get_structure("pred", "AF-P12345.pdb")
# Build plddt_dict from B-factors
plddt_dict = {}
for model in structure:
    for chain in model:
        for residue in chain:
            if "CA" in residue:
                key = (chain.id, residue.id[1])
                plddt_dict[key] = residue["CA"].bfactor

io = PDBIO()
io.set_structure(structure)
io.save("AF-P12345_confident.pdb", ConfidenceSelect(plddt_dict, 70.0))
```

## Key Parameters and Gotchas

### Confidence Interpretation
- **pLDDT > 90**: Very high confidence; reliable for detailed analysis and docking.
- **pLDDT 70-90**: Confidence correct backbone; sidechain orientations may be wrong.
- **pLDDT 50-70**: Low confidence; likely disordered or unstructured. Do not use for docking.
- **pLDDT < 50**: Predicted disordered; should be excluded from structural analysis.
- **PAE < 5 A**: Residues are confidently positioned relative to each other.
- **PAE > 20 A**: Relative domain orientation is unreliable even if individual pLDDT is high.

### Multimer Predictions
- AlphaFold-Multimer predictions require paired MSA construction. Unpaired MSAs alone yield poor interface predictions.
- Interface pLDDT is often lower than monomeric pLDDT. A separate interface confidence metric (ipTM) is available in AF2-ptm mode.
- AF3 handles protein-ligand and protein-nucleic acid complexes but requires specific input formatting.

### Running Predictions
- **MSA depth** is the primary driver of prediction quality. Sequences without close homologs in MSA databases will have lower confidence.
- **Recycles**: Default 3 recycles is sufficient for most proteins. Increasing to 6-12 may improve difficult targets at the cost of runtime.
- **Templates**: Enabling templates can improve accuracy for proteins with known structural homologs but may bias predictions away from novel folds.
- **GPU memory**: AlphaFold2 requires ~16 GB GPU RAM for a 1000-residue protein. ESMFold requires ~8 GB for similar size.

### Common Pitfalls
- **Disordered regions**: AlphaFold often predicts compact structures for intrinsically disordered regions (IDRs). Low pLDDT is the indicator, but the model may still appear folded in visualizations.
- **Oligomeric state**: AlphaFold2 (monomer) will predict single chains even for obligate oligomers. Use AlphaFold-Multimer or AF3 for complexes.
- **Cofactors and ligands**: AF2 does not predict ligand positions. AF3 does, but with varying accuracy. Consider docking onto the predicted scaffold.
- **Version differences**: AlphaFold DB v2 predictions differ from v4. Always check which model version was used when comparing predictions.
- **Batch downloads**: AlphaFold DB rate-limits requests. Use the FTP bulk download for large-scale analyses rather than individual HTTP requests.
