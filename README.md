# Tenbio — Metabolic Pathway Designer

Tenbio is a synthetic-biology design platform aimed at the gap between
**"I have a goal"** and **"I have a buildable construct."** A user
describes a goal in natural language ("Maak een organisme dat ammoniak
afbreekt naar N₂"), the platform translates it via a local LLM (Gemma
running in a sidecar container), grounds the parsed intent against KEGG
and UniProt, walks backwards through KEGG reactions to propose a
candidate pathway in the chosen chassis, predicts the production rate
via Flux Balance Analysis, and hands the resulting parts off to a
visual Pathway Designer with Gibson primer design and SBOL3 / GenBank
export ready for the wet lab.

The long-term ambition extends to designing synthetic-cell consortia
for problems like agricultural-runoff ammonia removal, photosynthetic
fuel production, precision-fermentation food proteins, PFAS
bioremediation, and recombinant blood-plasma components. See
[`TODO.md`](TODO.md) for the phased roadmap.

## Architecture

```
┌──────────────┐     ┌────────────────────────────────────────────┐
│   Frontend   │────▶│ API :8000 (FastAPI, SQLite)                │
│  React :3000 │     │                                            │
└──────────────┘     │  /api/v1/parts            CRUD parts       │
                     │  /api/v1/optimize/*       codon optimizer  │
                     │  /api/v1/igem|kegg|uniprot|pubmed          │
                     │  /api/v1/structure/*      route to GPUs    │
                     │  /api/v1/pathways/*       Pathway model    │
                     │  /api/v1/primers/gibson   primer designer  │
                     │  /api/v1/design/from-goal natural language │
                     │  /api/v1/design/from-compound  KEGG retro  │
                     │  /api/v1/design/chat/stream    SSE chat    │
                     │  /api/v1/simulate/fba     cobrapy FBA      │
                     └─────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼─────────────────────┐
        ▼                      ▼                     ▼
   protenix :8001          esm :8002              llm :8003
   AlphaFold 3 repro       ESMFold                FastAPI wrapper
   GPU                     GPU                          │
                                                        ▼
                                                 ollama :11434
                                                 Gemma weights
                                                 GPU
```

All services run under `docker compose`. GPU services need the NVIDIA
container toolkit. Without a GPU you can still run the frontend + api
and use everything except 3D structure prediction and the AI Designer
goal parser.

## Quick start

Requirements:
- Docker (Engine ≥ 24 with the v2 `docker compose` plugin) and the
  current user in the `docker` group
- For the AI Designer + structure prediction: an NVIDIA GPU, the
  proprietary driver, and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- ~10 GB free disk for images + model caches; the first AI Designer
  run pulls Gemma 9B (~5 GB) into the `ollama-models` volume

The repo ships a single helper script that wraps the common
`docker compose` invocations:

```bash
./start.sh up        # foreground, see all logs (Ctrl-C to stop)
./start.sh up -d     # background, return prompt
./start.sh status    # health + reachability of each service
./start.sh down      # stop everything (volumes preserved)
./start.sh help      # full command list
```

After `./start.sh up -d`, open <http://localhost:3000> in a browser.
The first launch takes a few minutes for image builds + the Gemma
pull; subsequent starts are seconds.

### Without a GPU

If you don't have an NVIDIA GPU available, run only the CPU services:

```bash
./start.sh up-cpu
```

This brings up `frontend` + `api` only. **Parts Library, Search
Databases, Pathway Designer, Codon Optimizer, exports, sequencing
import, primers** all work. **AI Designer** and **Structure
Predictor** tabs will return 503 — that's expected.

### Health check

```bash
./start.sh status
```

Reports container state plus an HTTP probe of every service's health
endpoint. Useful first stop when something feels off.

## How to use the app

The frontend is a single-page React app at
<http://localhost:3000> with six tabs along the top:

### 1. Parts Library
Browse the local genetic-parts database (promoters, RBS, terminators,
genes). Each part has a sequence, organism, source, and a "find
papers" link that calls PubMed. Use the **+ New part** button to add
your own; **Edit** / **Delete** are there too. Click a part for the
detail modal with the full sequence and copy-to-clipboard.

### 2. Search Databases
Unified search across local parts, **iGEM Registry** (BioBricks),
**KEGG** (pathways, enzymes, genes), and **UniProt** (proteins).
Anything you find can be imported into the local library with one
click.

### 3. AI Designer **(GPU required)**
This is the headline feature. Type a goal in any language Gemma
supports (Dutch examples are pre-loaded as one-click buttons):

- *"Maak een organisme dat uit mest de ammoniak haalt en omzet naar N₂"*
- *"Maak via fotosynthese componenten voor kerosine"*
- *"Maak de eiwitten om kaas te produceren"*
- *"Maak een organisme dat PFAS in water afbreekt"*
- *"Maak bacteriën die bloedplasma componenten produceren voor 0-negatief"*

Pick a host (default *E. coli*), BFS depth (how far back to walk
through KEGG reactions), and click **Parse goal**. You get back:

- An **Intent card** — target compound or protein with KEGG / UniProt
  links, candidate hosts, optimization metric, constraints, a
  **feasibility note** that's honest about biological limits (bacteria
  can't glycosylate, anammox is slow, PFAS is research-grade, etc.),
  and a confidence pill (green / yellow / red).
- A **Pathway result** — KEGG reactions producing your target,
  grouped by BFS depth (color-coded). Each row shows EC numbers,
  equation, and host candidate genes (already resolved from the
  organism's annotated genome via KEGG).

Select reactions you like and click **Use this design** — the genes
get pushed into the Pathway Designer canvas.

Below the design output is a **streaming chat** panel: ask the model
follow-up questions about the parsed intent. The chat is grounded
with the current intent so questions like *"Why is anammox so slow?"*
or *"Which host is best and why?"* get specific answers.

### 4. Pathway Designer
Drag parts onto the D3 canvas to assemble a multi-cassette construct.
Buttons across the top:

- **Import from KEGG** — same flow as AI Designer's hand-off, but
  starting from a KEGG pathway/gene rather than a goal.
- **Export GenBank / FASTA** — drop into SnapGene or Benchling.
- **Export SBOL3** — JSON-LD or RDF/XML.
- **Export plate map / assembly worklist** — CSVs for biolab liquid
  handlers (Opentrons / Hamilton).
- **Sequencing import** — drop a FASTQ or AB1 file from a sequencing
  vendor; the API parses it and reports alignment to your design.
- **Generate Gibson primers** — calls `/api/v1/primers/gibson` with
  the canvas's ordered fragments. Returns forward/reverse primers
  with homology overhangs and Tm.

### 5. Codon Optimizer
Paste a protein sequence + pick a host organism, get the
codon-optimized DNA sequence back. Currently bias-tuned for *E. coli*;
chassis-specific tables come with Phase 3 of the roadmap.

### 6. Structure Predictor **(GPU required)**
3D structure prediction. Two backends:

- **Protenix** (port 8001) — AlphaFold 3 reproduction, supports
  multi-chain assemblies (protein/DNA/RNA/ligand/ion). 8 model
  variants from `protenix_tiny` (135 M params, fast) to
  `protenix_base` (368 M, slower / more accurate).
- **ESMFold** (port 8002) — Meta's ESMFold v1, single-chain
  protein-only, much faster, a bit less accurate.

Submit a job, watch its status update, view the predicted CIF in the
embedded 3Dmol.js viewer. Confidence scores (pLDDT, pTM, ipTM) are
rendered alongside.

## Power-user surface

| Where | What |
|---|---|
| `./start.sh test` | Run pytest for the API + llm service inside their containers |
| `./start.sh logs api` | Tail just the API logs |
| `./start.sh shell api` | Open a shell inside the running api container — handy for `alembic upgrade head` etc. |
| `./start.sh build api` | Rebuild a single service after editing its Dockerfile |
| `./start.sh down --volumes` | Drop all data (parts.db, model caches, prediction outputs). Asks you to type "yes". |

API docs (auto-generated by FastAPI) are at
<http://localhost:8000/docs> once the api service is up. They list
every endpoint with try-it-out widgets — a fast way to explore the
backend independently of the React UI.

## Development setup

### API
The API uses [`uv`](https://github.com/astral-sh/uv) for dependency
management:

```bash
cd pathwaysfinder/api
uv sync                      # install / update everything from uv.lock
uv run python -m pytest      # run tests outside docker
uv run uvicorn app.main:app --reload   # run api outside docker
```

The Dockerfile still installs from `requirements.txt`, so new deps go
in **both** `pyproject.toml` (canonical) **and** `requirements.txt`.

### Frontend
```bash
cd pathwaysfinder/frontend
npm install
npm run dev      # http://localhost:5173 by default
npm run build    # tsc + vite build
```

By default the dev server proxies API calls to the backend's exposed
port. Set `VITE_API_URL` to override.

### Adding a chassis (Phase 2 / 3)
Drop the SBML file into `pathwaysfinder/api/data/models/<key>.xml`,
add a `ChassisModel` entry in
`pathwaysfinder/api/app/services/fba.py`'s `CHASSIS_REGISTRY`, and the
new chassis appears in `GET /api/v1/simulate/chassis` and is usable
via `POST /api/v1/simulate/fba`.

### Roadmap
Phases and concrete next steps are tracked in [`TODO.md`](TODO.md).
The four-phase plan toward natural-language pathway design is described
in [`pathwaysfinder/docs/llm-service-plan.md`](pathwaysfinder/docs/llm-service-plan.md).

## License & contact

Tenbio is in active development. See [`CLAUDE.md`](CLAUDE.md) for the
agent-collaboration guide used by Claude Code in this repository.
