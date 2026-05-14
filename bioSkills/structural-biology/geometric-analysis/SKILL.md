# Structural Biology: Geometric Analysis

Computing geometric and topological properties of macromolecular structures including distances, angles, dihedrals, surface areas, and volumes.

## Description

Geometric analysis encompasses measurement of intra- and inter-molecular distances, bond angles, torsion/dihedral angles, solvent-accessible and solvent-excluded surface areas, pocket/cavity detection, and volume calculations. These measurements are foundational for structure validation, docking studies, and understanding structure-function relationships.

## Recommended Tools

### Python Packages
- **BioPython** (`Bio.PDB`): Built-in distance/angle/dihedral calculations via `Vector` class
- **MDAnalysis**: Efficient geometric measurements on trajectories
- **MDTraj**: Fast dihedral and distance computations with NumPy broadcasting
- **gemmi**: Surface area and volume calculations on mmCIF structures
- **PyMOL** (`pymol` API): Scriptable geometric measurements and visualization
- **FreeSASA**: Solvent-accessible surface area computation (C library with Python bindings)
- **PyVOL**: Pocket detection and volume estimation
- **PyComCare**: Contact area and complementarity analysis

### CLI Tools
- **FreeSASA**: Command-line SASA calculation
- **MSMS**: Molecular surface computation (Michel Sanner's Molecular Surface)
- **CASTp**: Pocket/cavity detection web server with local tools
- **fpocket**: Fast pocket detection on PDB structures
- **DSSP**: Secondary structure assignment from geometry
- **pdbtools**: Quick geometric queries on PDB files

## Common Workflows

### Calculate inter-atomic distances

```python
from Bio.PDB import PDBParser
import numpy as np

parser = PDBParser(QUIET=True)
structure = parser.get_structure("1abc", "1abc.pdb")

def get_ca_coords(structure, model_id=0):
    """Extract C-alpha coordinates as a NumPy array."""
    model = structure[model_id]
    coords = []
    for chain in model:
        for residue in chain:
            if residue.id[0] == " " and "CA" in residue:
                coords.append(residue["CA"].coord)
    return np.array(coords)

coords = get_ca_coords(structure)

# Pairwise distance matrix
diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
dist_matrix = np.sqrt((diff ** 2).sum(axis=2))

# Find residue pairs within a cutoff
cutoff = 8.0  # Angstroms
pairs = np.argwhere((dist_matrix < cutoff) & (dist_matrix > 0))
```

### Compute backbone dihedral angles (Ramachandran)

```python
from Bio.PDB import PDBParser, calc_dihedral
import numpy as np

parser = PDBParser(QUIET=True)
structure = parser.get_structure("1abc", "1abc.pdb")

def compute_phi_psi(structure, model_id=0):
    """Compute phi and psi dihedral angles for each residue."""
    model = structure[model_id]
    phi_psi = []
    for chain in model:
        residues = [r for r in chain if r.id[0] == " " and "CA" in r]
        for i in range(1, len(residues) - 1):
            prev_res = residues[i - 1]
            curr_res = residues[i]
            next_res = residues[i + 1]
            # phi: C(i-1)-N(i)-CA(i)-C(i)
            phi = calc_dihedral(
                prev_res["C"].vector,
                curr_res["N"].vector,
                curr_res["CA"].vector,
                curr_res["C"].vector,
            )
            # psi: N(i)-CA(i)-C(i)-N(i+1)
            psi = calc_dihedral(
                curr_res["N"].vector,
                curr_res["CA"].vector,
                curr_res["C"].vector,
                next_res["N"].vector,
            )
            phi_psi.append((curr_res.resname, np.degrees(phi), np.degrees(psi)))
    return phi_psi

angles = compute_phi_psi(structure)
```

### Solvent-accessible surface area with FreeSASA

```python
import freesasa

structure = freesasa.Structure("1abc.pdb")
result = freesasa.calc(structure)

print(f"Total SASA: {result.totalArea():.2f} A^2")
for chain_id in structure.chainLabels():
    area = result.chainArea(chain_id)
    print(f"Chain {chain_id}: {area:.2f} A^2")
```

### Pocket detection with fpocket

```bash
# Run fpocket on a PDB structure
fpocket -f 1abc.pdb

# Results written to 1abc_out/pockets/
# Each pocket has volume, drugability score, and residue composition
```

### Compute SASA per-residue with MDTraj

```python
import mdtraj as md

traj = md.load("1abc.pdb")
sasas = md.shrake_rupley(traj)  # nm^2 per atom
# Convert to per-residue
topology = traj.topology
residue_sasa = {}
for residue in topology.residues:
    atom_indices = [atom.index for atom in residue.atoms]
    residue_sasa[residue] = sasas[0, atom_indices].sum() * 100  # nm^2 to A^2
```

## Key Parameters and Gotchas

### Distance and Angle Conventions
- **Distance units**: PDB coordinates are in Angstroms. MDTraj uses nanometers by default; always convert with `* 10` when comparing.
- **Dihedral angle conventions**: BioPython returns radians; convert with `numpy.degrees()`. Phi/psi definitions vary between tools -- verify atom ordering.
- **Minimum image convention**: For periodic systems (MD trajectories), always apply PBC corrections when computing distances. Use `mdtraj.compute_distances()` which handles this automatically.

### Surface Area
- **SASA vs SES**: Solvent-accessible surface area (SASA) includes the probe radius shell. Solvent-excluded surface (SES) is the molecular surface. These differ by ~10-20%.
- **Probe radius**: Standard probe radius is 1.4 A (water). Different values change absolute SASA but relative rankings are robust.
- **Resolution dependence**: Low-resolution structures (worse than 3 A) may have inaccurate sidechain positions, making SASA unreliable for those residues.

### Pocket Detection
- **fpocket parameters**: `-m` (minimum alpha sphere radius, default 3.0 A), `-M` (maximum alpha sphere radius, default 6.0 A). Adjust for small molecule vs protein-protein interfaces.
- **Volume estimates** depend heavily on the algorithm and probe radius. Compare relative volumes, not absolute values, across methods.
- **Cryptic pockets** may not be present in a single static structure. Ensemble docking or MD simulations are needed.

### Common Pitfalls
- **Missing atoms**: Structures with missing sidechain atoms will yield incorrect SASA and pocket volumes. Use `pdbfixer` or `MODELLER` to rebuild before analysis.
- **Alternate locations**: Atoms with multiple conformations must be resolved (select altloc) before geometric calculations.
- **Hydrogen atoms**: X-ray structures typically lack hydrogens. SASA calculations without H are still standard, but dihedral angles involving H (chi angles) require protonation first.
- **Chain breaks**: A gap in backbone atoms will produce incorrect phi/psi values. Check for chain continuity before computing dihedrals.
