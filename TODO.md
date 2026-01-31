# Tenbio Roadmap

## Parts Library Uitbreiden

- [ ] **Add detail view for parts**
  - Make parts clickable to show a modal or separate page with full details
  - Complete sequence with copy-to-clipboard
  - Metadata weergave
  - Links naar relevante research papers (PubMed, DOI)
  - References field toevoegen aan Part model

- [ ] **Add create/edit parts UI**
  - Form voor nieuwe parts aanmaken
  - Bestaande parts kunnen bewerken
  - Validatie voor required fields (name, type, sequence)

- [ ] **Import more iGEM parts**
  - Seed data uitbreiden met meer iGEM Registry parts
  - Eventueel iGEM API parsen voor bulk import

## Pathway Designer

- [ ] **Build Pathway Canvas with D3.js**
  - Interactieve D3.js canvas voor pathway design
  - Parts uit library naar canvas slepen
  - Visuele connecties tussen parts
  - Juiste volgorde afdwingen (promoter → RBS → gene → terminator)

## Backend / Database

- [ ] **Migrate to PostgreSQL**
  - SQLite vervangen door PostgreSQL
  - docker-compose.yml updaten
  - Alembic migrations opzetten

- [ ] **Add codon optimization endpoint**
  - POST /api/v1/optimize endpoint
  - Input: protein sequence + target organism
  - Output: codon-optimized DNA sequence
  - Biopython gebruiken

## External APIs

- [ ] **Integrate PubMed API for research papers**
  - PubMed/NCBI E-utilities API connectie
  - Automatisch gerelateerde papers zoeken per part
  - Zoeken op part name, gene name, keywords
  - Paper titles, authors, abstract preview, DOI links

- [ ] **Integrate iGEM Registry API**
  - Direct parts zoeken en importeren vanuit iGEM
  - external_apis/igem.py client

- [ ] **Integrate KEGG API for pathways**
  - Metabolic pathway data ophalen
  - Enzyme lookups
  - external_apis/kegg.py client

- [ ] **Integrate UniProt API for proteins**
  - Protein sequences en annotaties ophalen
  - external_apis/uniprot.py client

## ML / GPU (A6000)

- [ ] **Set up ESM-3 service**
  - ESM-3 protein language model opzetten
  - ml_service/esm3_service.py
  - Endpoints voor:
    - Structure prediction
    - Variant generation
    - Protein embeddings
