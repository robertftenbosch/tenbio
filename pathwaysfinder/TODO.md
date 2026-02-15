
## Voltooid

### Protenix Model Selectie & Preloading (2026-02-15)

- [x] Model registry met alle 8 Protenix modelvarianten (base, mini, tiny, constraint)
- [x] Per-job model selectie via `model_name` in prediction request
- [x] Model swap met GPU VRAM cleanup (`torch.cuda.empty_cache()`)
- [x] `POST /preload` endpoint voor eager model loading
- [x] `PRELOAD_MODEL` env var voor startup preloading
- [x] `GET /models` endpoint met volledige metadata (parameters, features, speed tier, loaded status)
- [x] `GET /health` toont welk model geladen is
- [x] Frontend: rich model selector met size badges, feature tags, speed tier indicator
- [x] Frontend: preload button met loading spinner en status polling

**Bestanden:**
- Backend: `protenix-service/app/prediction_worker.py` - `MODEL_CATALOG`, `get_runner()`, `preload_model()`
- Backend: `protenix-service/app/main.py` - `/preload`, `/models`, startup handler
- Backend: `protenix-service/app/schemas.py` - `ModelInfo`, `PreloadRequest`, `PreloadResponse`
- Frontend: `frontend/src/components/StructurePredictor/StructurePredictor.tsx`
- Frontend: `frontend/src/api/structure.ts` - `preloadModel()`
- Frontend: `frontend/src/types/structure.ts` - `ProtenixModel` met extra velden
- Docker: `protenix-service/Dockerfile`, `docker-compose.yml` - `PRELOAD_MODEL` env var

### ESMFold Service als tweede GPU optie (2026-02-15)

- [x] ESM service (`esm-service/`) met ESMFold structuurvoorspelling
- [x] Zelfde API contract als Protenix (predict, jobs, models, preload, health)
- [x] PDB naar CIF conversie via Biopython
- [x] Model preloading bij startup via `PRELOAD_MODEL=esmfold_v1`
- [x] API proxy routing: `protenix_*` -> Protenix (:8001), `esm*` -> ESM (:8002)
- [x] `GET /models` merged modellen van beide GPU services
- [x] Job tracking: API onthoudt welke service elk job_id bezit
- [x] Docker Compose met ESM service (poort 8002, GPU access)

**Bestanden:**
- ESM Service: `esm-service/app/main.py`, `prediction_worker.py`, `schemas.py`
- ESM Docker: `esm-service/Dockerfile`, `esm-service/requirements.txt`
- API Routing: `api/app/routes/structure.py` - `_get_service_url()`, `_job_service_map`
- Docker: `docker-compose.yml` - `esm` service + `ESM_SERVICE_URL` env var

---

## Open Issues

### KEGG Import - Genes niet gevonden (2026-01-31)

**Issue:** Bij het zoeken naar enzymen (bijv. "nitrogen") worden geen genes gevonden in de KEGG Import modal.

**Mogelijke oorzaken om te onderzoeken:**
1. De KEGG API endpoint `/link/{organism}/ec:{ec_number}` geeft mogelijk geen resultaten terug
2. Het organism code mapping kan incorrect zijn (ecoli -> eco, sce -> sce)
3. De enzyme EC nummers die terugkomen van de search zijn mogelijk niet gekoppeld aan genes in het gekozen organisme
4. API timeout of parsing issues

**Te testen:**
- Test de backend endpoint direct: `GET /api/v1/kegg/enzymes/{ec_number}/genes?organism=ecoli`
- Check de KEGG API response in de browser console
- Probeer specifieke EC nummers die bekend zijn in E. coli (bijv. 1.7.1.4 voor nitrate reductase)

**Bestanden:**
- Backend: `api/app/external_apis/kegg.py` - `get_enzyme_genes()` functie
- Backend route: `api/app/routes/kegg.py` - `/enzymes/{ec_number}/genes` endpoint
- Frontend: `frontend/src/components/PathwayCanvas/KeggImportModal.tsx`
- Frontend API: `frontend/src/api/external.ts` - `getKeggEnzymeGenes()`
