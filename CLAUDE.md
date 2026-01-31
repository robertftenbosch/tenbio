# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Tenbio is a **Metabolic Pathway Designer** - a web application for synthetic biology researchers to design genetic constructs for protein production in microorganisms. The project is currently in the planning/architecture phase with no implementation code yet.

## Long-Term Vision

The ultimate goal of Tenbio extends beyond pathway design into **synthetic cell engineering** for solving major societal challenges. The platform aims to enable the design of synthetic cells that harness bacterial processes powered by sunlight and nutrients to produce valuable compounds or break down harmful substances.

### Dream Applications

1. **Nitrogen Crisis Solution** - Engineer organisms that can process agricultural waste and manure surpluses (particularly relevant for the Netherlands' nitrogen crisis) by converting excess nitrogen into harmless or useful compounds

2. **Medical Bioproduction** - Design synthetic cells capable of producing blood plasma components for patients in need, reducing dependency on human donors

3. **Green Hydrogen Production** - Create photosynthetic organisms that efficiently convert sunlight and water into hydrogen gas as a sustainable energy source

### Enabling Technologies (Future Roadmap)

- **Photosynthetic pathway integration** - Import and optimize cyanobacterial/algal light-harvesting systems
- **Minimal cell chassis** - Design stripped-down synthetic cells optimized for specific production tasks
- **Metabolic flux optimization** - Model and optimize energy/nutrient flow for maximum output
- **Biosafety containment** - Built-in genetic safeguards for environmental release scenarios

These long-term goals inform the architecture decisions made today, ensuring the platform can scale from single protein production to complex multi-pathway synthetic organisms.

## Planned Architecture

```
Frontend (React + TypeScript)
         │
         ▼
    API Layer (FastAPI)
         │
         ▼
    Core Services
    ├── Pathway Engine      # Gene/enzyme pathway design
    ├── Sequence Optimizer  # Codon optimization
    ├── Simulation Engine   # Expression prediction
    └── Parts Registry      # Genetic parts database
         │
         ▼
    GPU/ML Layer (A6000 48GB)
    ├── ESM-3 Service       # Protein structure & variant generation
    ├── Embedding Service   # Protein embeddings for similarity search
    └── FAISS GPU           # Vector similarity search
         │
         ▼
    Data Layer
    ├── PostgreSQL (projects, pathways, simulations)
    ├── Redis (cache, Celery queue)
    └── S3/MinIO (sequences)
```

## Technology Stack

**Frontend:** React, TypeScript, D3.js (visualization), Zustand (state), Radix UI + Tailwind CSS

**Backend:** FastAPI, SQLAlchemy, Celery + Redis, Pydantic

**Bioinformatics:** biopython, cobra (FBA), sbol3

**ML/GPU:** ESM-3 (protein language model), FAISS GPU (vector search), PyTorch + CUDA

**Hardware:** NVIDIA A6000 (48GB VRAM) - supports ESM-3 + FAISS + batch inference

**External APIs:** KEGG (pathways), UniProt (proteins), iGEM (parts registry)

## Planned Directory Structure

```
frontend/src/
├── components/
│   ├── PathwayCanvas/    # D3.js pathway visualization
│   ├── SequenceEditor/   # DNA sequence editing
│   ├── PartsLibrary/     # Genetic parts browser
│   └── SimulationPanel/  # Results display
├── hooks/
└── stores/

api/
├── pathway_engine/       # Core pathway design logic
├── sequence_optimizer/   # Codon optimization
├── simulation_engine/    # Expression simulation
├── parts_registry/       # Parts database models
├── external_apis/        # KEGG, UniProt, iGEM clients
└── ml_service/           # GPU-accelerated ML services
    ├── esm3_service.py   # ESM-3 protein design
    └── embedding_service.py  # FAISS vector search
```

## ESM-3 Capabilities

The ML layer uses ESM-3 (EvolutionaryScale) for advanced protein engineering:

- **Structure Prediction**: Predict 3D protein structure from sequence
- **Variant Generation**: Generate optimized protein variants for better expression/stability
- **Motif Scaffolding**: Design new proteins around functional motifs
- **Inverse Folding**: Find optimal sequences for a desired 3D structure
- **Embeddings**: Semantic protein search via vector similarity

## Key Domain Concepts

- **Pathway**: A sequence of genes and regulatory parts to produce a target protein
- **Genetic Parts**: Promoters, RBS, terminators, genes (using BioBricks/iGEM conventions like BBa_J23100)
- **Codon Optimization**: Adapting DNA sequences for host organism codon usage
- **Host Organisms**: E. coli (BL21), yeast, cyanobacteria (Synechocystis), algae (Chlamydomonas) - each has different codon preferences, available enzymes, and metabolic capabilities (photosynthesis for cyanobacteria/algae)
- **SBOL/GenBank**: Standard export formats for synthetic biology

## API Conventions (Planned)

- REST endpoints at `/api/v1/{resource}`
- UUID primary keys
- JSONB for flexible data (genes, regulatory parts, simulation results)
- Async simulation via Celery workers

## Development Setup (When Implemented)

The project will use Docker Compose with services:
- `frontend` (port 3000)
- `api` (port 8000)
- `simulation_worker` (Celery)
- `ml_worker` (Celery + GPU for ESM-3 tasks)
- `db` (PostgreSQL)
- `redis`

## ML API Endpoints (Planned)

```
POST /api/v1/ml/structure      # Predict 3D structure
POST /api/v1/ml/variants       # Generate optimized variants
POST /api/v1/ml/scaffold       # Motif scaffolding
POST /api/v1/ml/inverse-fold   # Structure → sequence
POST /api/v1/ml/embedding      # Generate protein embedding
GET  /api/v1/ml/similar/{id}   # Find similar proteins
```
