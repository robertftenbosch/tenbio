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
that can be built in the wet lab. Reaching that requires four new
capability layers on top of the current parts/pathway/structure stack:

1. **Compound → pathway discovery** (Phase 1, KEGG-grounded reverse
   search) — **shipped**
2. **Quantitative production simulation** (Phase 2, FBA via `cobra`) —
   **partially shipped**: textbook E. coli core + `/simulate/fba` live;
   strain optimization, larger genome-scale models, and frontend panel
   still open
3. **Multi-domain chassis support** (Phase 3, yeast / fungal / mammalian
   hosts) — *gating step* for the cheese-proteins and blood-plasma
   classes of goals, which are biologically impossible in bacteria —
   **open**
4. **Natural-language goal interpretation** (Phase 4, LLM service via
   Gemma) — **shipped**

Without Phase 3 the platform stays bacterial-only and roughly **two of
the five validation queries (cheese, blood plasma) cannot be answered
with a buildable design** — only with a feasibility note saying "use a
non-bacterial host." Phase 3 unblocks that.

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
- [x] **Protenix** (AlphaFold 3 reproduction) — multi-chain
      protein/DNA/RNA/ligand, 8 model variants, per-job model selection,
      GPU VRAM-aware swapping
- [x] **ESMFold** as a faster single-chain alternative (`services/esm/`)
- [x] Unified API contract: `protenix_*` → :8001, `esm*` → :8002
- [x] Persistent prediction job state across API + worker restarts

### Phase 1 — Compound → pathway discovery (shipped)
- [x] **`POST /api/v1/design/from-compound`** — KEGG retrosynthetic BFS
      with hub-metabolite exclusion, EC → KO → gene resolution per host
      (PR #21)
- [x] Free-text or KEGG-ID resolution via `/find/compound`
- [x] Chassis-name → KEGG-organism-code mapping (eco / sce / syn / bsu /
      ppa / kla) for the design endpoints — note: this is a routing
      shim, not a full Chassis entity (that comes with Phase 3)

### Phase 4 — Natural-language LLM service (shipped)
Detailed plan: [`pathwaysfinder/docs/llm-service-plan.md`](pathwaysfinder/docs/llm-service-plan.md).

- [x] LLM service container at `services/llm/` running Gemma via Ollama
      on port 8003 (PR #20). `LLM_MODEL` env var defaults to
      `gemma4:e4b`; override e.g. to `gemma3:9b` for an older drop-in
      or `gemma3:4b` on low-VRAM machines.
- [x] `POST /goal/parse` returning structured `DesignIntent` JSON with
      KEGG/UniProt-grounded IDs (system prompt + post-hoc validation
      against pre-fetched candidate lists)
- [x] `POST /api/v1/design/from-goal` with `materialize=true` chaining
      to `/from-compound` so a single call goes from natural language
      to a buildable pathway candidate (PR #21)
- [x] Five validation queries (ammonia/manure, photosynthetic kerosene,
      cheese, PFAS, blood plasma) locked in as test fixtures
- [x] Frontend "AI Designer" tab — goal input, intent card, pathway
      result with selectable reactions, hand-off to Pathway Designer
      canvas (PR #22)
- [x] **Streaming chat** (`POST /api/v1/design/chat/stream` over SSE)
      with the current DesignIntent injected as system context for
      grounded follow-ups (PR #23)
- [ ] When Phase 3 lands, update `host_candidates` generation so
      suggestions are filtered against real chassis capability flags
      (no glycosylated proteins suggested in E. coli)

### Phase 2 — FBA via cobrapy (partially shipped)
- [x] `cobra>=0.29` in API dependencies (PR #25)
- [x] Chassis-model registry stub (`ChassisModel` dataclass with
      domain + biomass-objective). Currently lists `textbook` only —
      Phase 3 adds the rest.
- [x] **`POST /api/v1/simulate/fba`** — biomass / target-reaction
      objectives, knockouts, carbon-source override, top-N flux output,
      404/422/503 error paths
- [x] `GET /api/v1/simulate/chassis` — registry listing for the
      upcoming frontend chassis picker
- [x] Tests use cobra's bundled `textbook` model so CI doesn't need
      external SBML files

## Open

### Phase 2 follow-ups (the rest of FBA)
- [ ] **Drop genome-scale SBML files** into `pathwaysfinder/api/data/models/`
      and add the corresponding `ChassisModel` registry entries:
      - `iML1515.xml` (E. coli K-12 MG1655, current state-of-the-art)
      - `iMM904.xml` (S. cerevisiae)
      - `iLB1027_lipid.xml` (Pichia pastoris)
      - `iSynCJ816.xml` (Synechocystis sp. PCC 6803)
      - `iCHO2291.xml` (CHO-K1, mammalian — Phase 3 adjacent)
      Mount as a docker volume so the API image stays small.
- [ ] **`POST /api/v1/optimize/strain`** — wraps cobrapy's OptKnock and
      FSEOF. Input: pathway + production target + chassis. Output:
      ranked list of knockout sets / overexpression targets with
      predicted yield improvements. Slow (~minutes for non-trivial
      models) → reuse the `PredictionJob` pattern from structure
      prediction; promote that table from `prediction_jobs` to a
      generic `jobs` table.
- [ ] **Frontend simulation panel** — visualises FBA results: growth
      vs. production tradeoff curve (varying target_reaction lower
      bound), per-reaction flux table, knockout suggestions from
      `/optimize/strain`. Sits as a sub-panel on the Pathway Designer
      tab.
- [ ] **Integrate FBA into `/api/v1/design/from-goal`** — once a
      DesignIntent is materialized into a candidate pathway, optionally
      run FBA on that pathway in the suggested chassis and include the
      predicted growth + product flux in the response. Closes the
      "natural language → buildable design *with predicted production
      rate*" loop in a single call.
- [ ] **Pathway → reaction-set bridging** — `/simulate/fba` currently
      takes ad-hoc knockouts; we need a way to overlay a Tenbio
      `Pathway` (from the Pathway model) onto a chassis genome-scale
      model. Likely: each `PathwayPart` of type `gene` declares which
      EC numbers it covers, the FBA endpoint adds those reactions to
      the chassis if missing.

### Phase 3 — Multi-domain chassis support

Goal: extend the platform beyond bacteria so therapeutic-protein and
food-protein goals (cheese, blood plasma, immunoglobulins) become
buildable, not just "feasibility-noted as impossible." This is the
gating step for ~40% of the validation queries.

The current chassis registry is bacterial-first by design. Phase 3
broadens it across **three domains**:

- **Yeast / fungal** — *Pichia pastoris*, *Saccharomyces cerevisiae*,
  *Kluyveromyces lactis*, *Trichoderma reesei*, *Aspergillus niger*.
  Unlocks: glycosylated therapeutics (HSA, monoclonal Fab),
  precision-fermentation food proteins (caseins, chymosin, whey).
- **Photosynthetic** — *Synechocystis* sp. PCC 6803, *Synechococcus
  elongatus*, *Chlamydomonas reinhardtii*. Unlocks: light-driven
  production of fuels, alkanes, hydrogen.
- **Mammalian** — CHO-K1, HEK293. Unlocks: complex glycoproteins,
  immunoglobulins, factor VIII / IX, EPO. Needed for the
  "blood plasma" class of goals; significantly out of bacterial /
  yeast scope (no fermentation, requires bioreactor + serum-free
  media).

Concrete work:

- [ ] **Chassis model** — promote chassis from a free-text string on
      `Pathway` to a real entity: domain (bacterial / fungal /
      photosynthetic / mammalian), capabilities (glycosylation,
      secretion, photosynthesis, growth medium), codon usage table
      reference, default genome-scale model reference (links to the
      Phase 2 FBA model registry).
- [ ] **Codon tables** — bundle codon-usage tables for the chassis
      above. Update `services/codon_optimizer.py` to pick the right
      table per chassis instead of hard-coded E. coli.
- [ ] **PTM (post-translational modification) capability flags** —
      glycosylation, phosphorylation, gamma-carboxylation. Used by the
      LLM service `feasibility_note` and by the design endpoints to
      filter out impossible chassis/target combinations.
- [ ] **Mammalian-cell workflow note** — mammalian construct design is
      different (lentiviral vectors, stable transfection, no Gibson
      Assembly). v1 can punt: produce the construct sequence + flag
      "use a transient transfection workflow, not Gibson." v2 adds a
      separate cloning-strategy module.
- [ ] **Chassis-aware Gibson primer designer** — currently primer Tm
      defaults to 60 °C with NEB HiFi. Some yeast workflows use Golden
      Gate. Add `assembly_method` parameter to the primer endpoint.
- [ ] **Frontend chassis picker** — when creating a Pathway, pick from
      the real chassis registry (with capability badges) rather than a
      free-text input.

### Other open

- [ ] **Migrate from SQLite to PostgreSQL** — required before
      multi-user / production. `docker-compose.yml` and the API both
      currently target SQLite via the `api-data` volume.
- [ ] **Wire up ESM-3 (not just ESMFold).** ESMFold is structure-only.
      ESM-3 unlocks variant generation, motif scaffolding, inverse
      folding, and protein embeddings — the capabilities promised in
      `CLAUDE.md`. Likely a fourth GPU service alongside Protenix,
      ESMFold and the LLM.
- [ ] **GPU contention** — Protenix, ESMFold, and the LLM service all
      share one A6000. With three loaded models VRAM is tight. Add a
      cross-service lock at the API layer so only one heavy inference
      runs at a time.
- [ ] **User accounts and project storage** — no auth today; everything
      is single-tenant. Needed before any external collaborator can use
      the tool.
- [ ] **Job history UI** — `GET /api/v1/structure/jobs` exposes the
      data, no frontend view yet.
- [ ] **Inline "explain this part" buttons** — leverage the streaming
      chat endpoint from PartCard / PathwayCanvas for in-context
      explanations. Plan §10 v2 follow-up.
- [ ] **Browser-side LLM fallback (WebLLM)** — for privacy-sensitive
      pathway designs that shouldn't leave the browser. Plan §13 open
      question.

### Long-term vision (from `CLAUDE.md`)

These remain aspirational and require significant new infrastructure
beyond Phases 1–4 above:

- Photosynthetic pathway integration with proper light/dark modelling
  (cyanobacterial / algal light-harvesting)
- Minimal synthetic-cell chassis design
- Multi-species consortium FBA (steadycom, OptCom)
- Biosafety containment / kill-switch design

## Active issues

See [`pathwaysfinder/TODO.md`](pathwaysfinder/TODO.md) for issues
currently being investigated.
