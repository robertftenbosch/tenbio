"""Design routes — natural-language and compound-driven pathway design.

Two endpoints:

- POST /api/v1/design/from-compound: deterministic KEGG retrosynthetic
  BFS. No LLM. Given a target compound and host, returns candidate
  reactions producing the target with the host's gene assignments.

- POST /api/v1/design/from-goal: natural-language goal -> structured
  DesignIntent via the LLM service, optionally chained to /from-compound
  to materialize a candidate pathway in one round trip.

The two are independent; /from-goal works even if no LLM service is
running for callers who only need the deterministic search.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.external_apis import llm_client
from app.schemas.design import (
    DesignFromCompoundRequest,
    DesignFromGoalRequest,
    DesignFromGoalResponse,
    DesignIntent,
    PathwayCandidatesResponse,
    ReactionStep,
)
from app.services import goal_grounding, pathway_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/design", tags=["design"])


# Map common chassis names from LLM responses to KEGG organism codes.
# Conservative -- only well-known pairs. Anything else falls back to
# the request's `host` field.
_CHASSIS_TO_KEGG = {
    "e. coli": "eco",
    "escherichia coli": "eco",
    "ecoli": "eco",
    "bl21": "eco",
    "mg1655": "eco",
    "saccharomyces cerevisiae": "sce",
    "yeast": "sce",
    "synechocystis": "syn",
    "synechocystis pcc 6803": "syn",
    "synechocystis sp. pcc 6803": "syn",
    "bacillus subtilis": "bsu",
    "pichia pastoris": "ppa",
    "kluyveromyces lactis": "kla",
}


def _resolve_host(intent: DesignIntent, fallback: str) -> str:
    for cand in intent.host_candidates:
        key = cand.lower().strip()
        if key in _CHASSIS_TO_KEGG:
            return _CHASSIS_TO_KEGG[key]
    return fallback


def _to_pathway_response(raw: dict) -> PathwayCandidatesResponse:
    return PathwayCandidatesResponse(
        target=raw["target"],
        host=raw["host"],
        max_depth_used=raw["max_depth_used"],
        reactions=[ReactionStep(**r) for r in raw["reactions"]],
        notes=raw["notes"],
    )


# ---------------------------------------------------------------------------


@router.post("/from-compound", response_model=PathwayCandidatesResponse)
async def design_from_compound(req: DesignFromCompoundRequest):
    """Deterministic KEGG retrosynthetic search.

    Resolves the target compound (by KEGG ID or by name search), then
    walks backwards through KEGG reactions up to `max_depth`, collecting
    enzyme assignments and the host organism's annotated genes for each
    reaction's EC numbers.
    """
    cpd_id = await pathway_search.resolve_compound_id(req.compound)
    if not cpd_id:
        raise HTTPException(
            status_code=404,
            detail=f"No KEGG compound matched '{req.compound}'. Try a KEGG ID like cpd:C00014 or a more specific name.",
        )

    raw = await pathway_search.search_pathway(
        cpd_id, host_organism=req.host, max_depth=req.max_depth
    )
    return _to_pathway_response(raw)


# ---------------------------------------------------------------------------


@router.post("/from-goal", response_model=DesignFromGoalResponse)
async def design_from_goal(req: DesignFromGoalRequest):
    """Translate a natural-language goal into a structured DesignIntent.

    Pre-LLM grounding step: extract probable target keywords from the
    query, search KEGG (compounds) and UniProt (proteins), and pass the
    candidate IDs to the LLM. The LLM is constrained to only use IDs
    from that list; any IDs that escape are stripped on the LLM-service
    side.

    If `materialize=true` (default) and the parsed intent has a kegg_id,
    chain to /from-compound automatically so the response includes
    candidate reactions, not just a parsed intent.
    """
    if req.skip_grounding:
        kegg_candidates: list[dict] = []
        uniprot_candidates: list[dict] = []
    else:
        kegg_candidates, uniprot_candidates = await goal_grounding.build_candidates(
            req.query
        )

    try:
        result = await llm_client.parse_goal(
            req.query,
            candidate_kegg_ids=kegg_candidates,
            candidate_uniprot_ids=uniprot_candidates,
        )
    except llm_client.LLMServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))

    intent = DesignIntent(**result["intent"])

    pathway_response = None
    if req.materialize and intent.target.kegg_id:
        host = _resolve_host(intent, req.host)
        try:
            raw = await pathway_search.search_pathway(
                intent.target.kegg_id, host_organism=host, max_depth=req.max_depth
            )
            pathway_response = _to_pathway_response(raw)
        except Exception as e:
            # Materialization is a best-effort second step; if KEGG flakes
            # out we still want to return the parsed intent.
            logger.warning(f"Materialization failed for {intent.target.kegg_id}: {e}")

    return DesignFromGoalResponse(
        intent=intent,
        candidate_kegg_count=len(kegg_candidates),
        candidate_uniprot_count=len(uniprot_candidates),
        model_used=result.get("model_used"),
        pathway_candidates=pathway_response,
    )
