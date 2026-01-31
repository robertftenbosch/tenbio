# Metabolic Pathway Designer - Technische Architectuur

## Overzicht

Een webapplicatie waarmee synbio-onderzoekers genetische constructen kunnen ontwerpen voor eiwitproductie in micro-organismen.

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐        │
│  │ Pathway       │  │ Sequence      │  │ Simulatie     │        │
│  │ Visualisatie  │  │ Editor        │  │ Dashboard     │        │
│  └───────────────┘  └───────────────┘  └───────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐        │
│  │ /design       │  │ /simulate     │  │ /export       │        │
│  │ endpoints     │  │ endpoints     │  │ endpoints     │        │
│  └───────────────┘  └───────────────┘  └───────────────┘        │
│  ┌───────────────┐                                               │
│  │ /ml           │  ← ESM-3 protein design endpoints             │
│  │ endpoints     │                                               │
│  └───────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CORE SERVICES                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Pathway     │ │ Sequence    │ │ Simulation  │ │ Parts     │  │
│  │ Engine      │ │ Optimizer   │ │ Engine      │ │ Registry  │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     GPU/ML LAYER (A6000 48GB)                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ ESM-3       │ │ Structure   │ │ Embedding   │ │ Expression│  │
│  │ Service     │ │ Predictor   │ │ Service     │ │ Predictor │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ PostgreSQL  │ │ Redis       │ │ S3/Minio    │ │ External  │  │
│  │ (projecten) │ │ (cache)     │ │ (sequences) │ │ APIs      │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
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

### 3.5 ESM-3 ML Service (GPU)

Machine learning service voor geavanceerde eiwit-analyse en -design, draaiend op NVIDIA A6000 (48GB VRAM).

```python
# ml_service/esm3_service.py

from esm.models.esm3 import ESM3
from esm.sdk.api import ESMProtein, GenerationConfig
import torch

class ESM3Service:
    """
    ESM-3 integratie voor protein engineering.

    Hardware: NVIDIA A6000 (48GB VRAM)
    Model: ESM3-open (small) - ~8-12GB VRAM
    Licentie: Non-commercial (ESM3-open)
    """

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = ESM3.from_pretrained("esm3_sm_open_v1").to(self.device)

    def predict_structure(self, sequence: str) -> ProteinStructure:
        """
        Voorspel 3D structuur van eiwit.
        Vervangt aparte ESMFold call.
        """
        protein = ESMProtein(sequence=sequence)
        config = GenerationConfig(track="structure", num_steps=10)
        result = self.model.generate(protein, config)
        return ProteinStructure(
            pdb=result.to_pdb_string(),
            confidence=result.ptm,
            per_residue_confidence=result.plddt
        )

    def generate_variants(
        self,
        sequence: str,
        constraints: dict,
        num_variants: int = 5
    ) -> list[ProteinVariant]:
        """
        Genereer geoptimaliseerde eiwitvarianten.

        Constraints kunnen zijn:
        - preserve_regions: [(start, end), ...] - behoud deze regio's
        - optimize_for: ["solubility", "stability", "expression"]
        - avoid_epitopes: [...] - vermijd allergene epitopen
        """
        protein = ESMProtein(sequence=sequence)

        # Mask posities die geoptimaliseerd mogen worden
        if constraints.get("preserve_regions"):
            mask = self._create_preservation_mask(
                sequence,
                constraints["preserve_regions"]
            )
            protein = protein.with_mask(mask)

        variants = []
        for _ in range(num_variants):
            config = GenerationConfig(
                track="sequence",
                num_steps=16,
                temperature=0.7
            )
            variant = self.model.generate(protein, config)

            # Evalueer variant
            score = self._evaluate_variant(
                variant,
                constraints.get("optimize_for", [])
            )
            variants.append(ProteinVariant(
                sequence=variant.sequence,
                mutations=self._get_mutations(sequence, variant.sequence),
                predicted_improvements=score
            ))

        return sorted(variants, key=lambda v: v.predicted_improvements, reverse=True)

    def scaffold_motif(
        self,
        motif_sequence: str,
        motif_structure: str,
        scaffold_length: int = 100
    ) -> list[ProteinDesign]:
        """
        Ontwerp nieuw eiwit rondom een functioneel motief.

        Gebruik: behoud actief centrum maar ontwerp nieuwe scaffold
        voor betere stabiliteit of expressie.
        """
        # Creëer prompt met structuur constraint voor motief
        protein = ESMProtein.from_pdb(motif_structure)

        # Extend met masked residues
        protein = protein.extend_with_mask(
            n_terminal=scaffold_length // 2,
            c_terminal=scaffold_length // 2
        )

        config = GenerationConfig(
            track="sequence",
            num_steps=32,
            temperature=0.5  # Lager voor meer conservatief design
        )

        designs = []
        for _ in range(3):
            result = self.model.generate(protein, config)
            designs.append(ProteinDesign(
                sequence=result.sequence,
                structure=result.to_pdb_string(),
                motif_preserved=self._verify_motif(result, motif_sequence)
            ))

        return designs

    def inverse_fold(self, structure_pdb: str) -> list[str]:
        """
        Van 3D structuur naar optimale aminozuursequentie.

        Gebruik: gegeven een gewenste vouwing, vind de beste
        sequentie die stabiel is in de host.
        """
        protein = ESMProtein.from_pdb(structure_pdb)
        protein = protein.with_masked_sequence()  # Mask alle residues

        config = GenerationConfig(
            track="sequence",
            num_steps=16
        )

        sequences = []
        for temp in [0.3, 0.5, 0.7]:  # Verschillende temperaturen
            config.temperature = temp
            result = self.model.generate(protein, config)
            sequences.append(result.sequence)

        return sequences

    def get_embedding(self, sequence: str) -> torch.Tensor:
        """
        Genereer protein embedding voor similarity search.

        Gebruik met FAISS voor snelle vector search over
        parts library of UniProt.
        """
        protein = ESMProtein(sequence=sequence)
        with torch.no_grad():
            embedding = self.model.encode(protein)
        return embedding.mean(dim=0)  # Pool over residues

    def predict_expression(
        self,
        sequence: str,
        host: str
    ) -> ExpressionPrediction:
        """
        Voorspel expressieniveau gebaseerd op eiwit eigenschappen.

        Combineert ESM-3 structuur predictie met host-specifieke
        analyse (aggregatie, toxiciteit, metabole burden).
        """
        structure = self.predict_structure(sequence)

        # Analyseer problematische eigenschappen
        aggregation_prone = self._predict_aggregation(structure)
        has_rare_folds = self._check_rare_folds(structure, host)

        return ExpressionPrediction(
            predicted_yield=self._estimate_yield(
                aggregation_prone,
                has_rare_folds
            ),
            bottlenecks=self._identify_bottlenecks(structure, host),
            recommendations=self._generate_recommendations(
                sequence,
                structure,
                host
            )
        )


# Pydantic models voor type safety
from pydantic import BaseModel

class ProteinStructure(BaseModel):
    pdb: str
    confidence: float  # pTM score
    per_residue_confidence: list[float]  # pLDDT per residue

class ProteinVariant(BaseModel):
    sequence: str
    mutations: list[str]  # ["A23V", "K45R", ...]
    predicted_improvements: dict[str, float]

class ProteinDesign(BaseModel):
    sequence: str
    structure: str  # PDB format
    motif_preserved: bool

class ExpressionPrediction(BaseModel):
    predicted_yield: float  # mg/L
    bottlenecks: list[str]
    recommendations: list[str]
```

### 3.6 Embedding & Vector Search Service

Snelle similarity search over eiwitten en genetische onderdelen.

```python
# ml_service/embedding_service.py

import faiss
import numpy as np
from typing import Optional

class EmbeddingService:
    """
    Vector similarity search met FAISS (GPU-accelerated).

    Gebruikt ESM-3 embeddings voor semantische zoektocht
    over eiwitten en genetische onderdelen.
    """

    def __init__(self, esm3_service: ESM3Service):
        self.esm3 = esm3_service
        self.dimension = 1536  # ESM-3 embedding dimensie

        # GPU-accelerated FAISS index
        res = faiss.StandardGpuResources()
        self.index = faiss.GpuIndexFlatIP(res, self.dimension)

        self.id_mapping: dict[int, str] = {}  # FAISS idx → protein ID

    def index_protein(self, protein_id: str, sequence: str):
        """Voeg eiwit toe aan vector index."""
        embedding = self.esm3.get_embedding(sequence)
        embedding_np = embedding.cpu().numpy().reshape(1, -1)

        # Normaliseer voor cosine similarity
        faiss.normalize_L2(embedding_np)

        idx = self.index.ntotal
        self.index.add(embedding_np)
        self.id_mapping[idx] = protein_id

    def search_similar(
        self,
        query_sequence: str,
        k: int = 10,
        min_similarity: float = 0.5
    ) -> list[tuple[str, float]]:
        """
        Vind vergelijkbare eiwitten.

        Returns: [(protein_id, similarity_score), ...]
        """
        query_embedding = self.esm3.get_embedding(query_sequence)
        query_np = query_embedding.cpu().numpy().reshape(1, -1)
        faiss.normalize_L2(query_np)

        scores, indices = self.index.search(query_np, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if score >= min_similarity and idx in self.id_mapping:
                results.append((self.id_mapping[idx], float(score)))

        return results

    def semantic_search(
        self,
        query: str,
        protein_type: Optional[str] = None
    ) -> list[tuple[str, float]]:
        """
        Semantische zoektocht met natural language query.

        Voorbeeld: "thermostabiel enzym voor hoge temperatuur"

        Note: Vereist text-to-protein embedding model of
        vooraf gedefinieerde query templates.
        """
        # TODO: Implementeer met text encoder
        pass
```

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

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    volumes:
      - ./frontend/src:/app/src

  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/pathway_designer
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - ./api:/app

  simulation_worker:
    build: ./api
    command: celery -A tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/pathway_designer
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  # GPU Worker voor ML taken (ESM-3, embeddings, etc.)
  ml_worker:
    build: ./api
    command: celery -A ml_tasks worker --loglevel=info -Q ml_queue
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/pathway_designer
      - REDIS_URL=redis://redis:6379
      - CUDA_VISIBLE_DEVICES=0
      - ESM3_MODEL=esm3_sm_open_v1
    depends_on:
      - db
      - redis
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - ./api:/app
      - esm_model_cache:/root/.cache/huggingface  # Cache ESM-3 weights

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=pathway_designer
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  esm_model_cache:  # Persistent cache voor ESM-3 model weights
```

---

## 5.1 GPU Server Specificaties

**Hardware:** NVIDIA A6000 (48GB VRAM)

### VRAM Allocatie

| Model/Service | VRAM Usage | Concurrent |
|--------------|------------|------------|
| ESM-3 (small) | ~8-12GB | Ja |
| FAISS GPU Index | ~2-4GB | Ja |
| Batch inference buffer | ~8GB | - |
| **Totaal actief** | **~20-24GB** | - |
| **Beschikbaar voor grote batches** | **~24GB** | - |

### Configuratie

```yaml
# ml_config.yaml

esm3:
  model: "esm3_sm_open_v1"
  device: "cuda:0"
  max_sequence_length: 2048
  batch_size: 4
  cache_embeddings: true

faiss:
  use_gpu: true
  index_type: "IVF4096,Flat"  # Voor grote datasets
  nprobe: 64

inference:
  max_concurrent_requests: 4
  timeout_seconds: 300
  queue: "ml_queue"
```

---

## 6. MVP Scope

### Fase 1 (2-3 maanden): Proof of Concept

**Focus:** Albumine expressie in E. coli

- [ ] Simpele UI: kies target eiwit → krijg construct
- [ ] Hardcoded pathway voor albumine
- [ ] Codon optimalisatie
- [ ] Export naar GenBank formaat
- [ ] Basic simulatie (promoter sterkte alleen)

### Fase 2 (3-4 maanden): Uitbreiding

- [ ] Meerdere target eiwitten (stollingsfactoren, insuline)
- [ ] Pathway visualisatie canvas
- [ ] Parts library browser
- [ ] Meerdere host organismen (yeast)
- [ ] User accounts & projecten opslaan

### Fase 3 (4-6 maanden): Geavanceerd

- [ ] Automatische pathway discovery via KEGG
- [ ] Flux Balance Analysis simulatie
- [ ] Integratie met DNA synthesis bedrijven
- [ ] Lab protocol generator
- [ ] Team collaboration features

### Fase 4 (6+ maanden): ML-Enhanced Design

- [ ] ESM-3 structuurvoorspelling integratie
- [ ] Automatische variant generatie voor betere expressie
- [ ] Motif scaffolding voor enzyme engineering
- [ ] Semantische zoektocht over parts library
- [ ] Expression level prediction met ML

---

## 7. Tech Keuzes Samengevat

| Component | Keuze | Reden |
|-----------|-------|-------|
| Frontend | React + TypeScript | Ecosysteem, typing |
| Visualisatie | D3.js | Flexibiliteit voor custom grafieken |
| Backend | FastAPI (Python) | Bioinfo libraries, async support |
| Database | PostgreSQL | JSONB voor flexibele schemas |
| Queue | Redis + Celery | Async simulaties |
| Auth | JWT + API keys | Simpel, standaard |
| Deployment | Docker + fly.io of Railway | Makkelijk starten |
| **ML/AI** | **ESM-3** | **Multimodaal protein LM (seq+struct+func)** |
| **GPU** | **NVIDIA A6000 (48GB)** | **Ruim voor ESM-3 + FAISS + batching** |
| **Vector Search** | **FAISS GPU** | **Snelle similarity search** |

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

## Volgende Stap

Wil je dat ik een van deze onderdelen verder uitwerk? Bijvoorbeeld:

1. **Frontend prototype** - Werkende React app met pathway visualisatie
2. **API scaffold** - FastAPI project met basis endpoints
3. **Codon optimizer** - Werkende Python module
4. **Database seeding** - Script om parts registry te vullen met iGEM data
5. **ESM-3 service** - GPU worker met protein design capabilities
6. **Vector search setup** - FAISS index voor parts/protein similarity
