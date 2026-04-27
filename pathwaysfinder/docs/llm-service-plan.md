# LLM Service — Implementation Plan

A third GPU service alongside Protenix and ESMFold. Hosts the latest Gemma
(Gemma 4, falling back to Gemma 3 9B if the v4 weights are not yet
available at implementation time) and exposes a small, opinionated API
that the main API can call.

## 1. Goal

Make natural-language goals first-class input to the platform. Users
should be able to type things like:

- "Maak een organisme dat uit mest de ammoniak haalt en omzet naar N₂."
- "Maak via fotosynthese componenten voor kerosine."
- "Maak de eiwitten om kaas te produceren."
- "Maak een organisme dat PFAS in water afbreekt."
- "Maak bacteriën die bloedplasma componenten produceren voor 0-negatief."

The LLM service translates these into a **structured design intent**
(target compound or protein, host candidates, constraints, success
metric) and hands it to deterministic backend services (KEGG reverse
search, FBA, Pathway model). The LLM **never invents enzymes, EC numbers
or iGEM part IDs** — those come from grounded sources (KEGG, UniProt,
iGEM Registry).

The LLM is a translator and explainer, not a designer.

## 2. Scope

### v1 (this plan)

- One GPU container running Gemma via Ollama, OpenAI-compatible API
- Two task endpoints exposed by the LLM service:
  - `POST /goal/parse` — natural language → structured `DesignIntent` JSON
  - `POST /chat` — streaming chat with system prompt + optional context
- Two new endpoints in the main API:
  - `POST /api/v1/design/from-goal` — proxies through `/goal/parse` then
    calls the deterministic pathway designer
  - `POST /api/v1/design/from-compound` — deterministic, KEGG-based
    reverse pathway search (no LLM)
- Optional minimal frontend "AI Designer" tab

### v2 (future, not in this plan)

- Lab protocol generator (deterministic skeleton + LLM prose)
- Paper summarizer per Part / Pathway
- Biosafety check (rule-based + LLM rationale)
- Browser-side fallback via WebLLM for privacy-sensitive pathway designs

## 3. Architecture

```
┌──────────────┐     ┌────────────────┐
│   Frontend   │────▶│   API :8000    │
└──────────────┘     │                │
                     │  /design/from-goal────────┐
                     │  /design/from-compound    │
                     │  /pathways                │
                     │  /structure               │
                     └────────────────┘          │
                              │                  │
              ┌───────────────┼─────────────┐    │
              ▼               ▼             ▼    ▼
         protenix:8001    esm:8002      llm:8003
         (AlphaFold 3)    (ESMFold)     (Gemma)
```

The LLM container is a peer to the existing GPU services. Same Docker
network. Same `NVIDIA_VISIBLE_DEVICES` constraint as a known follow-up.

## 4. Model Choice

| Model | Params | INT4 VRAM | Use |
|---|---|---|---|
| **Gemma 4 9B (target)** | ~9B | ~5–6 GB | Primary, if released |
| Gemma 3 9B (fallback) | 9B | ~5.5 GB | Drop-in if v4 unavailable |
| Gemma 3 4B (constrained) | 4B | ~2.5 GB | If we need to share GPU with ESMFold loaded |
| Gemma 3 27B | 27B | ~16 GB | Quality, but eats most of the A6000 |

**Default**: Gemma 4 9B at INT4. Pinned via env var `LLM_MODEL` so we can
swap easily.

Why Gemma over Llama / Phi / Mistral?

- Native function-calling support
- Permissive license for commercial use
- Multi-language including Dutch (the user types in Dutch)
- Good size:quality ratio at 9B
- Active Google maintenance

## 5. Serving Stack

**v1: Ollama** — easiest setup, OpenAI-compatible server, GGUF model
download from the Ollama registry, native tool-calling support.

**v2 if perf is insufficient: vLLM** — much higher throughput,
PagedAttention, better batching. Same OpenAI API contract so the API
client doesn't need to change.

Decision driver: with one user at a time and short prompts, Ollama is
plenty (~30–60 tok/s on an A6000 for 9B INT4). Switch only if user
concurrency grows or response latency becomes a complaint.

## 6. API Surface

### LLM service (internal, port 8003)

```
POST /goal/parse       → structured DesignIntent
POST /chat             → streaming chat (SSE)
GET  /health           → model loaded, GPU ok
GET  /models           → available models
```

### Main API additions (public, port 8000)

```
POST /api/v1/design/from-goal       → DesignIntent + candidate Pathway(s)
POST /api/v1/design/from-compound   → deterministic, no LLM
GET  /api/v1/design/{intent_id}     → fetch a previously parsed intent
```

`from-goal` is a thin proxy:

```python
intent = await llm_client.parse_goal(text)
candidates = await design_from_compound(intent.target_compound, host=intent.host)
return {"intent": intent, "candidates": candidates}
```

### `DesignIntent` schema

```python
class DesignIntent(BaseModel):
    raw_query: str
    target: TargetSpec               # compound or protein
    host_candidates: list[str]       # ["E. coli", "Synechocystis", "P. pastoris"]
    optimization_metric: Literal["yield", "rate", "titer", "robustness"] | None
    constraints: list[str]           # ["photosynthetic", "open-environment release"]
    feasibility_note: str            # honest LLM caveat
    confidence: Literal["high", "medium", "low"]
```

```python
class TargetSpec(BaseModel):
    kind: Literal["compound", "protein", "removal"]
    name: str                        # human-readable
    kegg_id: str | None              # cpd:C00014 for ammonia, etc.
    uniprot_id: str | None           # for protein targets
    smiles: str | None
```

**The LLM must populate `kegg_id` from a vetted list**, not freeform.
The system prompt includes a small RAG snippet of likely KEGG IDs based
on keyword search of the user query *before* it hits the model.

## 7. Function Calling / Goal Parser

System prompt (abbreviated):

```
You are a metabolic engineering goal parser for a synthetic biology
platform. Your job is to translate a user's natural-language goal into
a JSON DesignIntent.

CONSTRAINTS:
- You MUST use only KEGG IDs and UniProt IDs from the candidate list
  provided in the user message. If a needed ID is not in the list, set
  the field to null and explain in feasibility_note.
- You NEVER invent enzyme EC numbers, gene names, or iGEM part codes.
- You DO comment honestly on feasibility:
  * Glycosylated proteins (immunoglobulins, factor VIII, EPO) cannot be
    produced in bacteria.
  * Photosynthesis requires a phototrophic chassis (Synechocystis,
    Chlamydomonas).
  * PFAS degradation is genuine cutting-edge research, very limited
    enzymes known.
- You output strict JSON matching the DesignIntent schema. No prose
  outside the JSON.
```

Pre-LLM RAG step: for the input query, run a keyword search against
KEGG `/find/compound` and UniProt to assemble a candidate list of IDs.
This list goes into the user message as context. The LLM then picks
from it instead of hallucinating.

Example flow for "haal ammoniak uit mest":

1. Keyword extraction → ["ammoniak", "ammonia", "manure", "mest"]
2. KEGG lookup → cpd:C00014 (ammonia), cpd:C01342 (ammonium), cpd:C00697 (NO₂), cpd:C00088 (nitrate)
3. Candidate list assembled, pushed to LLM
4. LLM returns:

```json
{
  "raw_query": "haal ammoniak uit mest",
  "target": {
    "kind": "removal",
    "name": "Ammonia (NH3) and ammonium (NH4+)",
    "kegg_id": "cpd:C00014"
  },
  "host_candidates": ["Kuenenia stuttgartiensis", "Brocadia anammoxidans", "engineered E. coli"],
  "optimization_metric": "rate",
  "constraints": ["agricultural-runoff context", "Netherlands nitrogen crisis"],
  "feasibility_note": "Anammox bacteria perform anaerobic NH4+ + NO2- → N2 oxidation. They grow extremely slowly (doubling 11 days). Engineered E. coli with anammox enzymes is an active research area but no robust strain exists yet.",
  "confidence": "medium"
}
```

The deterministic backend then takes this intent and looks up enzymes
for the relevant reactions in KEGG.

## 8. RAG Grounding

A prompt without grounding hallucinates. The LLM service does **not**
store its own knowledge base — it queries the main API on demand:

```
LLM service        Main API
    │                  │
    │  pre-parse       │
    │ ──KEGG search───▶│
    │ ◀──candidates────│
    │                  │
    │  build prompt    │
    │  call Gemma      │
    │                  │
    │  return intent   │
```

This keeps the LLM container stateless, which simplifies model swaps and
horizontal scaling.

## 9. Validation: Example Queries

Each of these is a smoke test for v1. The LLM service must produce a
DesignIntent whose feasibility_note matches the noted reality:

### 9.1 "Maak een organisme dat uit mest de ammoniak haalt → N₂"

- **Target**: cpd:C00014 (ammonia) removal
- **Hosts**: Anammox (Kuenenia, Brocadia), engineered E. coli, Pseudomonas
- **Reality check**: anammox is real but slow; nitrification + denitrification combo is more practical
- **Pathway leads**: hydrazine synthase (hzs), hydrazine dehydrogenase (hdh), nitrite reductase (nirS)

### 9.2 "Maak via fotosynthese kerosine-componenten"

- **Target**: C9–C16 alkanes (no single KEGG ID — alkane mixture)
- **Hosts**: Synechocystis sp. PCC 6803, Synechococcus elongatus
- **Reality check**: cyanobacterial alkane synthesis (aar/ado) gives C15–C17, productivity is the bottleneck
- **Pathway leads**: fatty acid → fatty acyl-CoA → fatty aldehyde (aar) → alkane (ado)

### 9.3 "Maak de eiwitten om kaas te produceren"

- **Target**: caseins (αs1, αs2, β, κ) + chymosin
- **Hosts**: Trichoderma reesei (Perfect Day pattern), Pichia pastoris, Kluyveromyces lactis
- **Reality check**: bacteria struggle with casein phosphorylation needed for micelle formation; chymosin is already industrial in Aspergillus niger
- **Pathway leads**: UniProt P02662 (αs1-casein), P00794 (chymosin)
- **feasibility_note** should mention "bacterial chassis won't form micelles, prefer fungal/yeast"

### 9.4 "Maak een organisme dat PFAS in water afbreekt"

- **Target**: per/polyfluorinated alkyl substances — no single KEGG ID
- **Hosts**: Pseudomonas, Acidimicrobium A6
- **Reality check**: cutting-edge, very few defluorination enzymes characterized; commercial degradation is far off
- **feasibility_note** should be honest: "limited enzymes known; this is research-grade, not a deployable design"
- **confidence**: low

### 9.5 "Maak bacteriën die bloedplasma componenten produceren (0-neg)"

- **Target**: human serum albumin + immunoglobulins
- **Hosts**: P. pastoris (HSA), CHO cells (immunoglobulins)
- **Reality check**: most plasma proteins need glycosylation that bacteria cannot do; HSA is the exception, already commercial in Pichia
- **feasibility_note**: "0-negative is a red blood cell antigen, not plasma. Plasma proteins are blood-group neutral. HSA is feasible in P. pastoris. Immunoglobulins need mammalian cells."

These five queries become the test fixtures for `tests/test_goal_parser.py`.

## 10. Frontend Integration

### v1 minimal

- New tab "AI Designer" (alongside existing five tabs)
- Single textarea for natural language input
- "Parse goal" button → calls `POST /api/v1/design/from-goal`
- Shows the returned `DesignIntent` as a card with chassis options + feasibility note
- "Use this design" button populates the existing Pathway Designer canvas

### v2 ideas (not in this plan)

- Side-panel chat that knows the current Pathway as context
- Inline "explain this part" buttons in PartCard / PathwayCanvas
- Streaming response via SSE for the chat endpoint

## 11. GPU Resource Planning

A6000 has 48 GB. Current load with all three GPU services running:

| Service | Model loaded | VRAM |
|---|---|---|
| Protenix (largest) | protenix_base 368M params | ~12–15 GB |
| ESMFold | esmfold_v1 690M params | ~3–4 GB |
| LLM | Gemma 9B INT4 | ~5–6 GB |
| KV cache + overhead | | ~3–5 GB |
| **Total** | | **~25–30 GB** |

We have headroom on a 48GB A6000. Concurrent inference is OK *as long
as* we're not also running Protenix + LLM at the same time on the
biggest models. Acceptable for v1.

Follow-up needed (already in TODO): GPU contention handling so we don't
oom on simultaneous predictions. The simplest mitigation is a shared
GPU lock at the API level — only one GPU service does heavy work at a
time, others queue. Out of scope for this plan but blocks heavy use.

## 12. Implementation Order — PR Breakdown

| PR | What | LOC est. |
|---|---|---|
| 1 | LLM service skeleton: Dockerfile (Ollama-based), `services/llm/app/main.py` exposing `/health`, `/chat`, `/goal/parse`. System prompt + DesignIntent schema. No grounding yet. | ~500 |
| 2 | `/api/v1/design/from-compound` — deterministic KEGG reverse lookup. No LLM dependency. Tests with mocked KEGG. | ~400 |
| 3 | KEGG candidate-builder for the LLM context. `/api/v1/design/from-goal` ties LLM service to from-compound. End-to-end tests for the five example queries (mocked LLM). | ~400 |
| 4 | Frontend: "AI Designer" tab with goal input + intent card + "use this design" hand-off to Pathway Designer canvas. | ~300 |
| 5 *(optional)* | LLM service: streaming `/chat` endpoint + SSE in frontend. Inline "explain this" buttons. | ~300 |

PRs 1–3 are independent enough to run in parallel. PR 4 depends on PRs
2+3 being merged. PR 5 is a follow-up.

## 13. Open Questions / Risks

1. **Will Gemma 4 weights be available at implementation time?** If not,
   ship with Gemma 3 9B and bump later via env var. The serving stack
   doesn't care.

2. **Hallucinated KEGG IDs.** Even with grounding + system prompt
   constraints, the LLM may still produce wrong IDs. Mitigation: every
   `DesignIntent` field that contains a KEGG/UniProt ID is validated
   against the actual API before returning. Invalid IDs become null
   with a note.

3. **Multi-language consistency.** Dutch input, English KEGG names —
   Gemma 9B handles both, but small inconsistencies expected. The
   `raw_query` field always preserves the original.

4. **Privacy of pathway designs.** All inference happens on the local
   A6000. No external API calls. This is a deliberate tradeoff vs. the
   higher quality of Anthropic / OpenAI models.

5. **Long-term: ESM-3 vs Gemma overlap.** ESM-3 (when integrated) does
   protein-specific design — variant generation, inverse folding. Gemma
   does goal interpretation and explanation. They are complements, not
   competitors. The plan keeps them as separate services.

6. **LLM as biosafety oracle.** Tempting but dangerous. v1 explicitly
   does not use the LLM for biosafety judgments. v2 may add it as a
   second-opinion layer on top of a rule-based check, never as the only
   gate.

## 14. Acceptance criteria for v1

- `docker compose up` brings up `llm` service alongside protenix + esm
- `POST /api/v1/design/from-goal` with each of the five example queries
  produces a DesignIntent whose `target.kegg_id` (when set) is verified
  against KEGG and `feasibility_note` matches the realities described
  in §9
- Frontend "AI Designer" tab can take a goal, render the intent, and
  populate the Pathway Designer canvas with the candidate parts
- All KEGG/UniProt IDs in the response are actually retrievable from
  the respective APIs (no hallucinated IDs reach the user)
