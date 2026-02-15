from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routes import parts, optimize, igem, kegg, uniprot

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Tenbio Pathways API",
    description="""
API for genetic parts and metabolic pathway design.

## Features

- **Parts Library**: Create, read, update, delete genetic parts (promoters, RBS, terminators, genes)
- **Codon Optimization**: Optimize DNA sequences for host organisms
- **iGEM Registry**: Search and import BioBrick parts from iGEM
- **KEGG Pathways**: Search metabolic pathways and enzymes
- **UniProt Proteins**: Search protein sequences and annotations

## External API Integration

- iGEM Registry (parts.igem.org)
- KEGG Database (kegg.jp)
- UniProt (uniprot.org)
- PubMed (ncbi.nlm.nih.gov)
""",
    version="0.2.0",
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(parts.router)
app.include_router(optimize.router)
app.include_router(igem.router)
app.include_router(kegg.router)
app.include_router(uniprot.router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
