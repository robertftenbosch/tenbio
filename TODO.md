# Tenbio Roadmap

Status overview at the project level. Day-to-day open issues live in
[`pathwaysfinder/TODO.md`](pathwaysfinder/TODO.md) — start there for items
that are actively being worked on.

## Delivered

### Parts Library
- [x] Part detail view with sequence + metadata (`PartDetailModal`)
- [x] Create / edit / delete UI for parts (`PartFormModal`)
- [x] Seed data with reference parts; bulk import via the iGEM Registry API
- [x] Linked PubMed search per part (paper titles, abstracts, DOIs)

### Pathway Designer
- [x] D3.js canvas (`PathwayCanvas`) with drag-and-drop assembly
- [x] KEGG pathway import modal (`KeggImportModal`)

### Backend / Codon Optimization
- [x] FastAPI service with the full `/api/v1/*` surface
- [x] `POST /api/v1/optimize/*` (protein → codon-optimized DNA, translate)
- [x] SBOL3 export, sequencing import (FASTQ / AB1)
- [x] CSV worklists for biolab machines

### External APIs
- [x] iGEM Registry — search, detail, single + batch import
- [x] KEGG — pathways, enzymes, genes (with EC → KO → gene fallback)
- [x] UniProt — protein search, sequences, features, EC lookups
- [x] PubMed — paper search per part / gene / keyword

### ML / GPU (A6000)
- [x] **Protenix** (AlphaFold 3 reproduction) — multi-chain protein/DNA/RNA/ligand,
      8 model variants, per-job model selection, GPU VRAM-aware swapping
- [x] **ESMFold** as a faster single-chain alternative (`services/esm/`)
- [x] Unified API contract: `protenix_*` → :8001, `esm*` → :8002
- [x] Persistent prediction job state across API + worker restarts

## Open

### Backend
- [ ] **Migrate from SQLite to PostgreSQL** — required before multi-user / production.
      `docker-compose.yml` and the API both currently target SQLite via the
      `api-data` volume.

### ML / GPU
- [ ] **Wire up ESM-3 (not just ESMFold).** ESMFold is structure-only.
      ESM-3 unlocks variant generation, motif scaffolding, inverse folding,
      and protein embeddings — the capabilities promised in `CLAUDE.md`.
      Likely a third GPU service alongside Protenix and ESMFold.
- [ ] **Resolve dual-GPU contention.** Both Protenix and ESMFold currently
      claim `NVIDIA_VISIBLE_DEVICES=all`; concurrent use can OOM the A6000.

### Platform
- [ ] **User accounts and project storage** — no auth today; everything is
      single-tenant. Needed before any external collaborator can use the tool.
- [ ] **Job history UI** — `GET /api/v1/structure/jobs` exposes the data,
      no frontend view yet.

### Long-term vision (from `CLAUDE.md`)
These remain aspirational and require significant new infrastructure:
- Photosynthetic pathway integration (cyanobacterial / algal light-harvesting)
- Minimal synthetic-cell chassis design
- Metabolic flux balance analysis (FBA via `cobra`)
- Biosafety containment / kill-switch design

## Active issues

See [`pathwaysfinder/TODO.md`](pathwaysfinder/TODO.md) for issues currently
being investigated.
