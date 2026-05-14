# Chemoinformatics

Molecular informatics for drug discovery: structure representation, similarity, filtering, and property prediction.

## Recommended Tools

- **RDKit**: core chemoinformatics toolkit (SMILES, mol, fingerprints)
- **datamol**: Pythonic RDKit wrapper with convenience functions
- **scikit-learn**: ML models for property prediction
- **DeepChem**: deep learning for molecular property prediction
- **MolVS**: molecular standardization and validation

## Common Workflows

### SMILES to Molecule and Fingerprints

```python
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

# Parse SMILES
mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")  # Aspirin
smiles = Chem.MolToSmiles(mol)
print(f"Canonical SMILES: {smiles}")

# Morgan (ECFP) fingerprint
fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)

# Molecular properties
print(f"MW: {Descriptors.MolWt(mol):.1f}")
print(f"LogP: {Descriptors.MolLogP(mol):.2f}")
print(f"HBA: {rdMolDescriptors.CalcNumHBA(mol)}")
print(f"HBD: {rdMolDescriptors.CalcNumHBD(mol)}")
print(f"TPSA: {rdMolDescriptors.CalcTPSA(mol):.1f}")
```

### Molecular Similarity Search

```python
from rdkit import DataStructs

# Tanimoto similarity between two molecules
fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, 2, nBits=2048)
fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, 2, nBits=2048)
similarity = DataStructs.TanimotoSimilarity(fp1, fp2)
print(f"Tanimoto similarity: {similarity:.3f}")

# Bulk similarity against a library
from rdkit.Chem import MolFromSmiles
library = [MolFromSmiles(s) for s in smiles_list]
library_fps = [AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048) for m in library]

query_fp = AllChem.GetMorganFingerprintAsBitVect(query_mol, 2, nBits=2048)
similarities = [DataStructs.TanimotoSimilarity(query_fp, fp) for fp in library_fps]
top_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)[:10]
```

### Drug-Likeness Filters (Lipinski, PAINS)

```python
from rdkit.Chem import Lipinski, rdMolDescriptors
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams

# Lipinski Rule of 5
def lipinski_pass(mol):
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    return mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10

# PAINS filter
params = FilterCatalogParams()
params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS_A)
catalog = FilterCatalog(params)
is_pains = catalog.HasMatch(mol)

# Veber filter (oral bioavailability)
def veber_pass(mol):
    tpsa = rdMolDescriptors.CalcTPSA(mol)
    rotors = rdMolDescriptors.CalcNumRotatableBonds(mol)
    return tpsa <= 140 and rotors <= 10
```

## Key Parameters

- Morgan fingerprint: radius=2 (ECFP4), nBits=2048 is standard
- Tanimoto > 0.7 generally indicates structural similarity
- Lipinski: MW<500, LogP<5, HBD<5, HBA<10
- PAINS: remove promiscuous binders from screening libraries
- TPSA < 140 A^2 for oral bioavailability (Veber)

## Gotchas

- Always canonicalize SMILES before comparison (MolToSmiles after MolFromSmiles)
- PAINS filters have false positives; do not discard without review
- Stereochemistry: include @ in SMILES for chiral centers; omit only if undefined
- Morgan radius 2 = ECFP4; radius 3 = ECFP6
- Salt forms: strip counterions with MolVS standardization before property calculation