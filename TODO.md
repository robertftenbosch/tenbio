# Tenbio Roadmap

Status overview at the project level. Day-to-day open issues live in
[`pathwaysfinder/TODO.md`](pathwaysfinder/TODO.md) — start there for items
that are actively being worked on.

## Long-term vision: natural-language pathway design

The platform's end goal is for users to express goals like:

- "Maak een organisme dat ammoniak uit mest haalt en omzet naar N₂."
- "Maak via fotosynthese componenten voor kerosine."
- "Maak de eiwitten om kaas te produceren."
- "Maak een organisme dat PFAS in water afbreekt."
- "Maak bacteriën die bloedplasma-eiwitten produceren voor 0-negatief."

…and have the platform translate those into concrete genetic constructs
that can be built in the wet lab. Reaching that requires three new
capability layers on top of the current parts/pathway/structure stack:

1. **Compound → pathway discovery** (Phase 1, KEGG-grounded reverse
   search)
2. **Quantitative production simulation** (Phase 2, FBA via `cobra`)
3. **Natural-language goal interpretation** (LLM service, see plan)

Each line below is roughly month-scale work. Honest constraint: many
"dream" outputs (immunoglobulins, complex glycoproteins) are
**biologically impossible in bacteria** and require a yeast / mammalian
chassis layer that the platform does not yet have.

## Delivered

### Parts Library
- [x] Part detail view with sequence + metadata (`PartDetailModal`)
- [x] Create / edit / delete UI for parts (`PartFormModal`)
- [x] Seed data with reference parts; bulk import via the iGEM Registry API
- [x] Linked PubMed search per part (paper titles, abstracts, DOIs)

### Pathway Designer
- [x] D3.js canvas (`PathwayCanvas`) with drag-and-drop assembly
- [x] KEGG pathway import modal (`KeggImportModal`)
- [x] First-class `Pathway` model with Alembic migrations
- [x] GenBank + FASTA + SBOL3 export
- [x] Gibson Assembly primer designer (`/api/v1/primers/gibson`)

### Backend / Codon Optimization
- [x] FastAPI service with the full `/api/v1/*` surface
- [x] `POST /api/v1/optimize/*` (protein → codon-optimized DNA, translate)
- [x] CSV worklists for biolab machines
- [x] Sequencing import (FASTQ / AB1) with alignment

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

### Phase 1 — Compound → pathway discovery

Goal: a user picks a target compound or protein and the platform
proposes a candidate pathway and chassis.

- [ ] **`POST /api/v1/design/from-compound`** — input: KEGG compound ID
      (or name) + host. Output: list of candidate pathways as ordered
      enzyme graphs derived from KEGG reactions.
- [ ] KEGG reverse-lookup helper: compound → reactions producing it →
      enzymes (EC) → genes for the chosen organism. Reuses the
      EC → KO → gene fallback already in place.
- [ ] Chassis registry — keep this small but real: E. coli BL21 / MG1655,
      S. cerevisiae, P. pastoris, Synechocystis sp. PCC 6803, B. subtilis.
      Each with codon-table reference and rough capability tags
      (photosynthetic, secretion-friendly, glycosylation-capable).
- [ ] Frontend: "AI Designer" tab that wraps both `/from-compound` and
      `/from-goal` (see LLM service).

### Phase 2 — FBA via `cobra` / cobrapy

Goal: predict whether a candidate pathway actually produces the target
at a useful rate, and find knockouts / overexpressions that improve it.

- [ ] Add `cobra>=0.29` to API dependencies. (Note: requires `glpk` or
      `cplex` as the LP solver — `glpk` is the open-source default.)
- [ ] **Genome-scale model registry** — bundle reference SBML models for
      common chassis:
      - `iML1515` (E. coli K-12, current state-of-the-art)
      - `iMM904` (S. cerevisiae)
      - `iLB1027_lipid` or `iCH360` (Pichia pastoris if available)
      - `iSyn669` or `iSynCJ816` (Synechocystis sp. PCC 6803)
      - Models live in `pathwaysfinder/api/data/models/*.xml`, mounted
        as a docker volume so they don't bloat the image.
- [ ] **`POST /api/v1/simulate/fba`** — input: pathway_id (or ad-hoc
      reaction set) + chassis + carbon source. Output: predicted growth
      rate + product flux + flux distribution.
- [ ] **`POST /api/v1/optimize/strain`** — wraps OptKnock and FSEOF
      from cobrapy. Input: pathway + production target. Output:
      ranked list of knockouts / overexpressions with predicted yield
      improvements.
- [ ] Frontend: simulation panel showing growth/production tradeoff
      curve and per-reaction flux table.
- [ ] Async via Celery? FBA is fast (~seconds); strain design is slow
      (~minutes). Reuse the existing structure-prediction job pattern
      for the slow case — `PredictionJob` table can become generic
      `Job` table.
- [ ] Tests using a small toy E. coli core model (`textbook_model`
      from cobra, ~95 reactions) so CI doesn't need to load iML1515.

### Phase 3 — Natural-language LLM service

Detailed plan: [`pathwaysfinder/docs/llm-service-plan.md`](pathwaysfinder/docs/llm-service-plan.md).

- [ ] LLM service container at `services/llm/` running latest Gemma
      (Gemma 4 9B target, fallback Gemma 3 9B) via Ollama. Port 8003.
- [ ] `POST /goal/parse` (LLM-side) → `DesignIntent` JSON with
      KEGG/UniProt-grounded IDs.
- [ ] `POST /api/v1/design/from-goal` (main API) — parses the goal then
      hands off to `/from-compound`.
- [ ] Five validation queries (see plan §9) used as test fixtures.
- [ ] Frontend "AI Designer" tab that takes natural language and
      pre-fills the Pathway Designer canvas with the candidate design.

### Other open

- [ ] **Migrate from SQLite to PostgreSQL** — required before
      multi-user / production. `docker-compose.yml` and the API both
      currently target SQLite via the `api-data` volume.
- [ ] **Wire up ESM-3 (not just ESMFold).** ESMFold is structure-only.
      ESM-3 unlocks variant generation, motif scaffolding, inverse
      folding, and protein embeddings — the capabilities promised in
      `CLAUDE.md`. Likely a fourth GPU service alongside Protenix,
      ESMFold and the LLM.
- [ ] **GPU contention** — Protenix, ESMFold, and the planned LLM
      service all share one A6000. With three loaded models VRAM is
      tight. Add a cross-service lock at the API layer so only one heavy
      inference runs at a time.
- [ ] **User accounts and project storage** — no auth today; everything
      is single-tenant. Needed before any external collaborator can use
      the tool.
- [ ] **Job history UI** — `GET /api/v1/structure/jobs` exposes the
      data, no frontend view yet.
- [ ] **Chassis expansion to non-bacterial hosts** — most blood plasma /
      glycoprotein use cases are biologically impossible in bacteria.
      Adding P. pastoris and CHO awareness (codon tables + capability
      flags + maybe a separate workflow) is the gating step for the
      "make therapeutic protein" class of goals.

### Long-term vision (from `CLAUDE.md`)

These remain aspirational and require significant new infrastructure
beyond Phases 1–3 above:

- Photosynthetic pathway integration with proper light/dark modelling
  (cyanobacterial / algal light-harvesting)
- Minimal synthetic-cell chassis design
- Multi-species consortium FBA (steadycom, OptCom)
- Biosafety containment / kill-switch design

## Active issues

See [`pathwaysfinder/TODO.md`](pathwaysfinder/TODO.md) for issues
currently being investigated.
