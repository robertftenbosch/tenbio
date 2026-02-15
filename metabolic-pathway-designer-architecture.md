# Metabolic Pathway Designer - Technische Architectuur

## Overzicht

Een webapplicatie waarmee synbio-onderzoekers genetische constructen kunnen ontwerpen voor eiwitproductie in micro-organismen.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (:3000)                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Parts       │ │ Pathway     │ │ Codon       │ │ Structure │  │
│  │ Library     │ │ Designer    │ │ Optimizer   │ │ Predictor │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
│  ┌─────────────┐                                                 │
│  │ Unified     │                                                 │
│  │ Search      │                                                 │
│  └─────────────┘                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API SERVICE (:8000)                           │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐        │
│  │ /parts        │  │ /optimize     │  │ /structure    │        │
│  │ CRUD + search │  │ codon optim.  │  │ proxy→protenix│        │
│  └───────────────┘  └───────────────┘  └───────────────┘        │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐        │
│  │ /kegg         │  │ /uniprot      │  │ /igem         │        │
│  │ pathways/enz. │  │ proteins      │  │ biobricks     │        │
│  └───────────────┘  └───────────────┘  └───────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────┐ ┌──────────────────────────────┐
│    PROTENIX GPU SERVICE (:8001)  │ │    ESM GPU SERVICE (:8002)    │
│  ┌──────────┐ ┌──────────┐      │ │  ┌──────────┐ ┌──────────┐  │
│  │ Model    │ │ Predict  │      │ │  │ ESMFold  │ │ Predict  │  │
│  │ Registry │ │ Worker   │      │ │  │ Model    │ │ Worker   │  │
│  │ (8 mod.) │ │          │      │ │  │          │ │          │  │
│  └──────────┘ └──────────┘      │ │  └──────────┘ └──────────┘  │
│  Multi-chain complexen          │ │  Single-chain protein only   │
│  AlphaFold 3 (diffusion)        │ │  ESMFold (single pass)       │
└──────────────────────────────────┘ └──────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ SQLite      │ │ Protenix    │ │ Model       │ │ External  │  │
│  │ (parts DB)  │ │ Output CIFs │ │ Checkpoints │ │ APIs      │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
│                                                                   │
│  Externe APIs: KEGG, UniProt, iGEM, PubMed                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Frontend

### Tech Stack
- **Framework:** React + TypeScript
- **Visualisatie:** D3.js voor pathway grafieken
- **Sequence viewer:** Custom component of openchemlib
- **State management:** Zustand (simpeler dan Redux)
- **UI componenten:** Radix UI + Tailwind CSS

### Hoofdcomponenten

```typescript
// Structuur
src/
├── components/
│   ├── PathwayCanvas/       // Visuele pathway editor
│   │   ├── Node.tsx         // Gen/enzym nodes
│   │   ├── Edge.tsx         // Reactie-pijlen
│   │   └── Canvas.tsx       // Drag-drop canvas
│   ├── SequenceEditor/      // DNA sequence weergave
│   │   ├── SequenceView.tsx
│   │   ├── AnnotationLayer.tsx
│   │   └── CodonOptimizer.tsx
│   ├── PartsLibrary/        // Doorzoekbare onderdelen
│   │   ├── PartCard.tsx
│   │   ├── SearchFilter.tsx
│   │   └── PartDetails.tsx
│   └── SimulationPanel/     // Resultaten simulatie
│       ├── YieldGraph.tsx
│       ├── BottleneckView.tsx
│       └── Recommendations.tsx
├── hooks/
│   ├── usePathway.ts
│   ├── useSimulation.ts
│   └── useParts.ts
└── stores/
    ├── projectStore.ts
    └── simulationStore.ts
```

---

## 2. API Layer

### Tech Stack
- **Framework:** FastAPI (Python) - goed ecosysteem voor bioinfo
- **Auth:** JWT tokens + API keys voor integraties
- **Docs:** Automatisch via OpenAPI/Swagger

### Endpoints

```python
# Pathway Design
POST   /api/v1/design/pathway          # Genereer pathway voor target eiwit
GET    /api/v1/design/pathway/{id}     # Haal pathway op
PUT    /api/v1/design/pathway/{id}     # Update pathway
POST   /api/v1/design/optimize         # Optimaliseer bestaand ontwerp

# Parts Registry
GET    /api/v1/parts/search            # Zoek genetische onderdelen
GET    /api/v1/parts/{id}              # Detail van onderdeel
GET    /api/v1/parts/promoters         # Lijst promoters voor organisme
GET    /api/v1/parts/terminators       # Lijst terminators

# Simulation
POST   /api/v1/simulate/expression     # Simuleer eiwitexpressie
POST   /api/v1/simulate/metabolic      # Simuleer metabole flux
GET    /api/v1/simulate/result/{id}    # Haal resultaat op (async)

# Export
POST   /api/v1/export/genbank          # Export naar GenBank formaat
POST   /api/v1/export/sbol             # Export naar SBOL formaat
POST   /api/v1/export/protocol         # Genereer lab protocol

# Projects
GET    /api/v1/projects                # Lijst projecten
POST   /api/v1/projects                # Nieuw project
GET    /api/v1/projects/{id}           # Project details

# ML/ESM-3 (GPU-accelerated)
POST   /api/v1/ml/structure            # Voorspel 3D structuur
POST   /api/v1/ml/variants             # Genereer geoptimaliseerde varianten
POST   /api/v1/ml/scaffold             # Motif scaffolding
POST   /api/v1/ml/inverse-fold         # Structuur → sequentie
POST   /api/v1/ml/embedding            # Genereer protein embedding
GET    /api/v1/ml/similar/{id}         # Vind vergelijkbare eiwitten
POST   /api/v1/ml/expression           # Voorspel expressieniveau
```

### Request/Response Voorbeeld

```python
# POST /api/v1/design/pathway
# Request:
{
    "target_protein": "human_serum_albumin",
    "host_organism": "e_coli_bl21",
    "optimization_goals": ["yield", "stability"],
    "constraints": {
        "max_genes": 5,
        "avoid_rare_codons": true
    }
}

# Response:
{
    "pathway_id": "pw_abc123",
    "genes": [
        {
            "name": "HSA",
            "source_organism": "homo_sapiens",
            "codon_optimized": true,
            "sequence_id": "seq_001"
        }
    ],
    "regulatory_parts": {
        "promoter": {"id": "BBa_J23100", "strength": "high"},
        "rbs": {"id": "BBa_B0034", "strength": "medium"},
        "terminator": {"id": "BBa_B0015"}
    },
    "predicted_yield": {
        "value": 150,
        "unit": "mg/L",
        "confidence": 0.7
    },
    "warnings": [
        "HSA bevat disulfide bridges - overweeg co-expressie van DsbA/DsbC"
    ]
}
```

---

## 3. Core Services

### 3.1 Pathway Engine

Verantwoordelijk voor het vinden van de juiste genen en enzymen.

```python
# pathway_engine/core.py

class PathwayEngine:
    def __init__(self):
        self.kegg_client = KEGGClient()
        self.uniprot_client = UniProtClient()
        self.parts_registry = PartsRegistry()
    
    def design_pathway(
        self,
        target: str,
        host: str,
        constraints: dict
    ) -> Pathway:
        """
        1. Zoek target eiwit in UniProt
        2. Vind benodigde biosynthese pathway in KEGG
        3. Identificeer welke enzymen al in host aanwezig zijn
        4. Selecteer heterologe genen voor ontbrekende stappen
        5. Kies optimale regulatory parts
        """
        
        # Stap 1: Target identificatie
        target_protein = self.uniprot_client.get_protein(target)
        
        # Stap 2: Pathway lookup
        if target_protein.is_simple_expression():
            # Direct expressie (bijv. albumine)
            pathway = self.create_expression_construct(target_protein)
        else:
            # Biosynthese pathway nodig
            pathway = self.kegg_client.find_pathway(target)
        
        # Stap 3: Gap analysis
        host_enzymes = self.get_host_enzymes(host)
        missing = pathway.get_missing_enzymes(host_enzymes)
        
        # Stap 4: Gene selection
        for enzyme in missing:
            best_gene = self.select_best_homolog(
                enzyme, 
                criteria=['expression_level', 'solubility']
            )
            pathway.add_gene(best_gene)
        
        # Stap 5: Regulatory parts
        pathway.add_regulatory_parts(
            self.parts_registry.get_optimal_parts(host, constraints)
        )
        
        return pathway
```

### 3.2 Sequence Optimizer

Optimaliseert DNA sequenties voor de gekozen host.

```python
# sequence_optimizer/codon_optimizer.py

class CodonOptimizer:
    def __init__(self, host_organism: str):
        self.codon_table = self.load_codon_usage(host_organism)
        self.forbidden_sequences = [
            "GAATTC",  # EcoRI site
            "AAGCTT",  # HindIII site
            # etc.
        ]
    
    def optimize(self, protein_sequence: str) -> str:
        """
        Optimaliseer codons voor expressie in host.
        
        Overwegingen:
        - Codon usage bias van host
        - mRNA secundaire structuur
        - Vermijd restriction sites
        - GC content balanceren
        """
        dna_sequence = ""
        
        for amino_acid in protein_sequence:
            codon = self.select_optimal_codon(
                amino_acid,
                context=dna_sequence[-20:]  # lokale context
            )
            dna_sequence += codon
        
        # Post-processing
        dna_sequence = self.remove_forbidden_sites(dna_sequence)
        dna_sequence = self.optimize_mrna_structure(dna_sequence)
        
        return dna_sequence
    
    def calculate_cai(self, sequence: str) -> float:
        """Codon Adaptation Index - maat voor optimalisatie."""
        pass
```

### 3.3 Simulation Engine

Voorspelt of het ontwerp gaat werken.

```python
# simulation_engine/expression_model.py

class ExpressionSimulator:
    """
    Simpel model voor eiwitexpressie.
    Later uit te breiden met FBA (Flux Balance Analysis).
    """
    
    def simulate(self, pathway: Pathway, host: str) -> SimulationResult:
        # Promoter sterkte
        transcription_rate = self.get_transcription_rate(
            pathway.promoter,
            pathway.gene_copy_number
        )
        
        # RBS sterkte → translatie
        translation_rate = self.predict_rbs_strength(
            pathway.rbs,
            pathway.mrna_structure
        )
        
        # Protein folding / stability
        folding_efficiency = self.predict_folding(
            pathway.target_protein,
            host
        )
        
        # Metabolic burden
        burden = self.calculate_metabolic_burden(pathway)
        growth_penalty = self.growth_rate_reduction(burden)
        
        # Final yield prediction
        yield_estimate = (
            transcription_rate 
            * translation_rate 
            * folding_efficiency 
            * (1 - growth_penalty)
        )
        
        return SimulationResult(
            predicted_yield=yield_estimate,
            bottlenecks=self.identify_bottlenecks(pathway),
            recommendations=self.generate_recommendations(pathway)
        )
```

### 3.4 Parts Registry

Database van genetische onderdelen.

```python
# parts_registry/models.py

from sqlalchemy import Column, String, Float, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class GeneticPart(Base):
    __tablename__ = 'genetic_parts'
    
    id = Column(String, primary_key=True)  # bijv. "BBa_J23100"
    type = Column(String)  # promoter, rbs, terminator, gene
    name = Column(String)
    description = Column(String)
    sequence = Column(String)
    
    # Metadata
    source_organism = Column(String)
    compatible_hosts = Column(JSON)  # ["e_coli", "yeast", ...]
    
    # Karakteristieken
    strength = Column(Float)  # 0-1, relatieve sterkte
    reliability = Column(Float)  # hoe goed gedocumenteerd
    
    # SBOL compliance
    sbol_uri = Column(String)
    
    # Usage stats
    times_used = Column(Integer)
    success_rate = Column(Float)
```

### 3.5 Protenix Structure Prediction Service (GPU) -- GEIMPLEMENTEERD

GPU-accelerated 3D structuurvoorspelling via Protenix (AlphaFold 3 reproductie door ByteDance).
Draait als aparte microservice op poort 8001.

**Beschikbare modellen:**

| Model | Parameters | Features | Snelheid |
|-------|-----------|----------|----------|
| `protenix_base_default_v1.0.0` | 368M | MSA + Template + RNA MSA | Langzaam (200 stappen, 10 cycles) |
| `protenix_base_20250630_v1.0.0` | 368M | MSA + Template + RNA MSA (nieuwere PDB data) | Langzaam |
| `protenix_base_default_v0.5.0` | 368M | MSA | Langzaam |
| `protenix_base_constraint_v0.5.0` | 368M | MSA + Constraints (pocket/contact) | Langzaam |
| `protenix_mini_esm_v0.5.0` | 135M | ESM + MSA (geen MSA search nodig) | Snel (5 stappen, 4 cycles) |
| `protenix_mini_ism_v0.5.0` | 135M | ISM + MSA | Snel |
| `protenix_mini_default_v0.5.0` | 134M | MSA | Snel |
| `protenix_tiny_default_v0.5.0` | 110M | MSA | Snelst |

**Architectuur:**

```python
# services/protenix/app/prediction_worker.py

# Model Registry -- slechts 1 model geladen per keer (GPU VRAM beperking)
MODEL_CATALOG = {
    "protenix_base_default_v1.0.0": {
        "parameters_m": 368.48,
        "features": ["MSA", "Template", "RNA MSA"],
        "speed_tier": "slow",
        "n_step": 200, "n_cycle": 10,
    },
    # ... 7 andere modelvarianten
}

def get_runner(model_name: str):
    """Laad model, swap als ander model gevraagd wordt.
    Bij swap: del runner, torch.cuda.empty_cache(), dan nieuw model laden."""

def preload_model(model_name: str):
    """Eager loading voor eliminatie cold-start delay."""
```

**API Endpoints (poort 8001):**

```
GET  /health           # GPU status + welk model geladen is
GET  /models           # Alle 8 modellen met metadata en loaded status
POST /predict          # Submit prediction job (met model_name keuze)
GET  /jobs/{id}        # Poll job status
GET  /jobs/{id}/structure  # Download voorspelde CIF structuur
POST /preload          # Preload model naar GPU (async, fire-and-forget)
```

**Environment variabelen:**
- `PRELOAD_MODEL` -- model dat bij startup geladen wordt (default: `protenix_base_default_v1.0.0`)
- `PROTENIX_OUTPUT_DIR` -- output directory voor CIF bestanden

**Ondersteunde chain types:** protein, DNA, RNA, ligand (CCD/SMILES), ion

**Confidence scores:** pLDDT (0-100), pTM (0-1), ipTM (0-1), ranking score

### 3.6 ESM Structure Prediction Service (GPU) -- GEIMPLEMENTEERD

Snelle structuurvoorspelling via ESMFold (Meta AI). Draait als aparte microservice op poort 8002.
Ideaal voor snelle single-chain protein previews zonder MSA search.

**Beschikbare modellen:**

| Model | Parameters | Features | Snelheid |
|-------|-----------|----------|----------|
| `esmfold_v1` | 690M | Protein (single-chain) | Zeer snel (single forward pass) |

**Verschil met Protenix:**
- ESMFold: alleen enkelvoudige eiwitketens, geen complexen (geen DNA/RNA/ligand/ion)
- ESMFold: geen MSA search nodig, directe sequentie-naar-structuur voorspelling
- ESMFold: sneller maar minder nauwkeurig voor grote complexen
- Protenix: volledige multi-chain complexen, MSA + Template features, nauwkeuriger

**Architectuur:**

```python
# services/esm/app/prediction_worker.py

MODEL_CATALOG = {
    "esmfold_v1": {
        "parameters_m": 690.0,
        "features": ["Protein"],
        "speed_tier": "fast",
    },
}

def get_model(model_name: str):
    """Laad ESMFold model met GPU swap support."""

def _run_esmfold(sequence: str, output_dir: str):
    """ESMFold inference: sequentie -> PDB -> CIF conversie."""
```

**API Endpoints (poort 8002):** Zelfde contract als Protenix service.

**Routing:** De API service (:8000) routeert automatisch op basis van model naam prefix:
- `protenix_*` modellen -> Protenix service (:8001)
- `esm*` modellen -> ESM service (:8002)

### 3.7 Toekomstige ML Features

Geplande uitbreidingen voor de ESM service:

- Automatische variant generatie voor betere expressie
- Motif scaffolding voor enzyme engineering
- Inverse folding (structuur naar sequentie)
- Protein embeddings voor similarity search (FAISS)
- Expression level prediction

---

## 4. Data Layer

### 4.1 PostgreSQL Schema

```sql
-- Users & Projects
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    organization VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR NOT NULL,
    description TEXT,
    host_organism VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Pathway designs
CREATE TABLE pathways (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id),
    target_protein VARCHAR NOT NULL,
    genes JSONB,  -- Array van gene objects
    regulatory_parts JSONB,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Simulation results
CREATE TABLE simulations (
    id UUID PRIMARY KEY,
    pathway_id UUID REFERENCES pathways(id),
    parameters JSONB,
    results JSONB,
    status VARCHAR,  -- pending, running, completed, failed
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Parts registry (lokale cache + custom parts)
CREATE TABLE parts (
    id VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,
    name VARCHAR,
    sequence TEXT NOT NULL,
    metadata JSONB,
    source VARCHAR,  -- 'igem', 'addgene', 'custom'
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 4.2 Externe Data Bronnen

```python
# external_apis/clients.py

class KEGGClient:
    """KEGG Pathway Database API"""
    BASE_URL = "https://rest.kegg.jp"
    
    def get_pathway(self, pathway_id: str) -> dict:
        pass
    
    def find_pathway_for_compound(self, compound: str) -> list:
        pass


class UniProtClient:
    """UniProt Protein Database API"""
    BASE_URL = "https://rest.uniprot.org"
    
    def get_protein(self, accession: str) -> Protein:
        pass
    
    def search_proteins(self, query: str) -> list:
        pass


class IGEMClient:
    """iGEM Parts Registry"""
    
    def get_part(self, part_id: str) -> GeneticPart:
        pass
    
    def search_parts(self, type: str, organism: str) -> list:
        pass
```

---

## 5. Deployment

### Docker Compose (Huidige Configuratie)

```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    volumes:
      - ./api:/app
      - api-data:/app/data
    environment:
      - DATABASE_URL=sqlite:///./data/parts.db
      - PROTENIX_SERVICE_URL=http://protenix:8001
      - ESM_SERVICE_URL=http://esm:8002

  protenix:
    build: ./services/protenix
    ports:
      - "8001:8001"
    volumes:
      - protenix-cache:/root/checkpoint
      - protenix-output:/app/output
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - PROTENIX_OUTPUT_DIR=/app/output
      - PRELOAD_MODEL=protenix_base_default_v1.0.0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  esm:
    build: ./services/esm
    ports:
      - "8002:8002"
    volumes:
      - esm-cache:/root/.cache
      - esm-output:/app/output
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - ESM_OUTPUT_DIR=/app/output
      - PRELOAD_MODEL=esmfold_v1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - api

volumes:
  api-data:
  protenix-cache:       # Cached Protenix model checkpoints
  protenix-output:      # Predicted CIF structures (Protenix)
  esm-cache:            # Cached ESMFold model weights
  esm-output:           # Predicted structures (ESM)
```

---

## 5.1 GPU Services Details

### VRAM Gebruik per Model

| Service | Model Variant | Parameters | Geschat VRAM |
|---------|--------------|-----------|-------------|
| Protenix | `protenix_base_*` | 368M | ~8-12GB |
| Protenix | `protenix_mini_*` | 135M | ~4-6GB |
| Protenix | `protenix_tiny_*` | 110M | ~3-5GB |
| ESM | `esmfold_v1` | 690M | ~8-16GB |

**Beperking:** Elk service laadt slechts 1 model tegelijk. Bij model swap: `del model` + `torch.cuda.empty_cache()`.

**Let op:** Beide GPU services draaien op dezelfde GPU. Bij gelijktijdig gebruik kan VRAM tekort optreden. Start alleen de service die je nodig hebt, of gebruik de preload functie om te wisselen.

### Configuratie

```yaml
# Protenix service environment
PRELOAD_MODEL: protenix_base_default_v1.0.0
PROTENIX_OUTPUT_DIR: /app/output

# ESM service environment
PRELOAD_MODEL: esmfold_v1
ESM_OUTPUT_DIR: /app/output

# API service environment (routing)
PROTENIX_SERVICE_URL: http://protenix:8001
ESM_SERVICE_URL: http://esm:8002
```

---

## 6. MVP Scope & Voortgang

### Fase 1: Basis Platform -- VOLTOOID

- [x] Parts Library: CRUD, zoeken, filteren op type/organisme
- [x] Codon optimalisatie (meest frequent / gewogen strategie)
- [x] DNA translatie
- [x] Export naar FASTA en GenBank formaat
- [x] Unified Search over lokale parts, KEGG, UniProt, iGEM
- [x] SQLite database voor parts

### Fase 2: Pathway Design & External APIs -- VOLTOOID

- [x] Pathway Designer met drag-and-drop canvas
- [x] Visuele volgorde (Promoter -> RBS -> Gene -> Terminator)
- [x] KEGG pathway import via modal
- [x] UniProt eiwit search en import
- [x] iGEM BioBrick search en import
- [x] PubMed literatuur zoeken per part
- [x] Meerdere host organismen (E. coli, yeast)

### Fase 3: Structure Prediction -- VOLTOOID

- [x] Protenix (AlphaFold 3) integratie als GPU microservice
- [x] Multi-chain support (protein, DNA, RNA, ligand, ion)
- [x] 3D structuur visualisatie met 3Dmol.js
- [x] Confidence scores (pLDDT, pTM, ipTM, ranking)
- [x] Model selectie (8 Protenix varianten: base/mini/tiny/constraint)
- [x] Model preloading naar GPU met status feedback
- [x] Docker Compose met GPU reservering

### Fase 3b: ESMFold Service -- VOLTOOID

- [x] ESMFold structuurvoorspelling als aparte GPU microservice (:8002)
- [x] Zelfde API contract als Protenix (predict, jobs, models, preload)
- [x] API routing layer: automatisch routeren op basis van model prefix
- [x] Model preloading bij startup via `PRELOAD_MODEL` env var
- [x] PDB naar CIF conversie voor consistente output
- [x] Docker Compose met beide GPU services

### Fase 4: Nog te doen

- [ ] KEGG import bug fixen (genes niet gevonden)
- [ ] User accounts & projecten opslaan
- [ ] ESM-3 variant generatie en inverse folding
- [ ] Flux Balance Analysis simulatie
- [ ] Lab protocol generator
- [ ] Team collaboration features

---

## 7. Tech Keuzes Samengevat

| Component | Keuze | Status |
|-----------|-------|--------|
| Frontend | React 18 + TypeScript + Vite | Actief |
| Styling | Tailwind CSS 3.4 | Actief |
| 3D Viewer | 3Dmol.js | Actief |
| Backend API | FastAPI + SQLAlchemy + SQLite | Actief |
| Structure Prediction | Protenix (AlphaFold 3) + ESMFold | Actief |
| GPU Services | 2x PyTorch + CUDA containers (Protenix :8001, ESM :8002) | Actief |
| External APIs | KEGG, UniProt, iGEM, PubMed (via httpx) | Actief |
| Deployment | Docker Compose (3 services) | Actief |
| **ML/AI (toekomstig)** | **ESM-3 variant generatie, inverse folding** | **Gepland** |
| **Vector Search (toekomstig)** | **FAISS GPU** | **Gepland** |

---

## 8. Belangrijke Python Libraries

```txt
# api/requirements.txt

# Web framework
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.0

# Database
sqlalchemy==2.0.25
asyncpg==0.29.0
alembic==1.13.0

# Bioinformatics
biopython==1.83
cobra==0.29.0          # FBA simulaties
sbol3==1.1             # SBOL standaard

# Background tasks
celery==5.3.6
redis==5.0.1

# Externe APIs
httpx==0.26.0
tenacity==8.2.3        # Retry logic

# Utils
pyyaml==6.0.1
python-jose==3.3.0     # JWT
```

```txt
# api/requirements-ml.txt (GPU worker)

# PyTorch met CUDA support
--extra-index-url https://download.pytorch.org/whl/cu121
torch==2.2.0+cu121

# ESM-3 (EvolutionaryScale)
esm>=3.0.0             # ESM-3 models

# Vector search
faiss-gpu==1.7.4       # GPU-accelerated similarity search

# ML utilities
transformers>=4.36.0   # Hugging Face ecosystem
accelerate>=0.25.0     # Model loading optimization
safetensors>=0.4.0     # Fast model weight loading

# Numeriek
numpy>=1.24.0
scipy>=1.11.0
```

---

## Volgende Stappen

1. **KEGG Import bug fixen** -- genes worden niet gevonden bij enzyme search
2. **ESM-3 service** -- GPU worker voor protein design (variant generatie, inverse folding)
3. **User accounts & projecten** -- opslaan en delen van ontwerpen
4. **Vector search** -- FAISS index voor similarity search over parts library
5. **Flux Balance Analysis** -- metabole flux simulatie voor pathway optimalisatie
