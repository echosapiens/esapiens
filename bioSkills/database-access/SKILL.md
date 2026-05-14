# Database Access

Query public bioinformatics databases programmatically for sequences, structures, variants, and functional annotations.

## Recommended Tools

- **Bio.Entrez** (Biopython): NCBI Entrez (GenBank, PubMed, Gene, SRA)
- **gget**: unified CLI/Python interface to 20+ databases
- **requests**: direct API access to UniProt, Ensembl, PDB, etc.
- **bioservices**: Python interface to 40+ bioinformatics web services

## Common Workflows

### NCBI Entrez (Biopython)

```python
from Bio import Entrez
Entrez.email = "your@email.com"

# Search PubMed
handle = Entrez.esearch(db="pubmed", term="BRCA1 breast cancer", retmax=10)
ids = Entrez.read(handle)["IdList"]

# Fetch records
handle = Entrez.efetch(db="pubmed", id=ids, rettype="abstract")
records = Entrez.read(handle)

# Fetch gene sequences
handle = Entrez.efetch(db="nucleotide", id="NM_007294", rettype="fasta")
seq_record = handle.read()
```

### UniProt REST API

```python
import requests

# Get protein entry
r = requests.get("https://rest.uniprot.org/uniprotkb/P38398.json")
data = r.json()
print(f"Protein: {data['proteinDescription']['recommendedName']['fullName']['value']}")

# Search by gene name
r = requests.get("https://rest.uniprot.org/uniprotkb/search?query=gene:BRCA1+AND+organism_id:9606&format=json")
results = r.json()
```

### Ensembl REST API

```python
import requests

server = "https://rest.ensembl.org"

# Get gene info
r = requests.get(f"{server}/lookup/symbol/homo_sapiens/BRCA1?content-type=application/json")
gene = r.json()

# Get sequence
r = requests.get(f"{server}/sequence/id/{gene['id']}?content-type=application/json")
seq = r.json()
```

### PDB (3D Structure) Access

```python
from Bio.PDB import PDBList

pdbl = PDBList()
pdbl.retrieve_pdb_file("1TUP", pdir=".", file_format="pdb")
```

## Key Parameters

- Entrez requires email; rate limit 3 requests/second without API key
- UniProt: use `+AND+organism_id:9606` for human specificity
- Ensembl: add `content-type=application/json` header for JSON response
- PDB: 4-character alphanumeric IDs (e.g., 1TUP, 6LU7)

## Gotchas

- Always set Entrez.email or your requests will be blocked
- Rate limits: NCBI 3/s (10/s with key), UniProt 10/s
- Use `retmax` to control result pagination
- UniProt changed from XML to JSON REST API in 2022; use v3 endpoints
- Caching is essential for repeated queries; use local SQLite or Redis