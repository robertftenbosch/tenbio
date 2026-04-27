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
from fastapi.responses import StreamingResponse

from app.external_apis import llm_client
from app.schemas.design import (
    ChatStreamRequest,
    DesignFromCompoundRequest,
    DesignFromGoalRequest,
    DesignFromGoalResponse,
    DesignIntent,
    FBASummary,
    PathwayCandidatesResponse,
    ReactionStep,
)
from app.services import fba, goal_grounding, pathway_search

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


# Map KEGG organism codes to FBA chassis registry keys. Only chassis
# whose SBML is in the FBA registry can be FBA'd; everything else
# silently falls through (no fba field on the response).
_KEGG_TO_FBA_CHASSIS: dict[str, str] = {
    "eco": "textbook",
    # Phase 3 will add: "sce" -> "iMM904", "syn" -> "iSynCJ816",
    # "ppa" -> "iLB1027_lipid", etc.
}


def _run_intent_fba(intent: DesignIntent, kegg_organism: str) -> FBASummary | None:
    """Best-effort FBA on the chassis matching the intent.

    Returns an FBASummary when the resolved chassis is in the FBA
    registry, None otherwise. Any exception inside cobra is caught and
    surfaced as None — the natural-language flow shouldn't break because
    the LP solver hiccupped.
    """
    chassis_key = _KEGG_TO_FBA_CHASSIS.get(kegg_organism)
    if not chassis_key:
        return None

    try:
        # Find a target exchange first; needs the loaded model.
        model = fba.get_model(chassis_key)
        target = fba.find_target_exchange(
            model, intent.target.kegg_id, intent.target.name
        )

        if target:
            result = fba.run_fba(
                chassis_key,
                target_reaction=target,
                objective="target",
                flux_limit=1,  # we don't need the flux distribution here
            )
        else:
            result = fba.run_fba(chassis_key, flux_limit=1)
    except Exception as e:
        logger.warning(f"Intent FBA on chassis '{chassis_key}' failed: {e}")
        return None

    return FBASummary(
        chassis=result.chassis,
        objective_id=result.objective_id,
        objective_value=result.objective_value,
        growth_rate=result.growth_rate,
        target_reaction=result.target_reaction,
        target_flux=result.target_flux,
        status=result.status,
        notes=result.notes,
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
    fba_summary: FBASummary | None = None
    host = _resolve_host(intent, req.host)
    if req.materialize and intent.target.kegg_id:
        try:
            raw = await pathway_search.search_pathway(
                intent.target.kegg_id, host_organism=host, max_depth=req.max_depth
            )
            pathway_response = _to_pathway_response(raw)
        except Exception as e:
            # Materialization is a best-effort second step; if KEGG flakes
            # out we still want to return the parsed intent.
            logger.warning(f"Materialization failed for {intent.target.kegg_id}: {e}")

    # FBA is independent of the KEGG pathway materialization — even when
    # the KEGG retro search returns nothing, a chassis-level biomass FBA
    # tells the user "yes the chosen host can grow on default media."
    if req.materialize:
        fba_summary = _run_intent_fba(intent, host)

    return DesignFromGoalResponse(
        intent=intent,
        candidate_kegg_count=len(kegg_candidates),
        candidate_uniprot_count=len(uniprot_candidates),
        model_used=result.get("model_used"),
        pathway_candidates=pathway_response,
        fba=fba_summary,
    )


# ---------------------------------------------------------------------------


_CHAT_SYSTEM_PROMPT = (
    "You are a synthetic-biology assistant inside the Tenbio platform. "
    "Answer concisely (3-6 sentences unless the user asks for more) and "
    "stay grounded in real biology: don't invent EC numbers, gene IDs, "
    "or iGEM part codes. If the user asks something outside synthetic "
    "biology, politely redirect. Match the user's language."
)


def _intent_context(intent: DesignIntent) -> str:
    """Render a DesignIntent as a compact system-message preamble."""
    parts = [
        f"User is currently looking at this parsed design intent:",
        f"  query: {intent.raw_query!r}",
        f"  target: {intent.target.name} ({intent.target.kind})",
    ]
    if intent.target.kegg_id:
        parts.append(f"  kegg_id: {intent.target.kegg_id}")
    if intent.target.uniprot_id:
        parts.append(f"  uniprot_id: {intent.target.uniprot_id}")
    parts.append(f"  candidate hosts: {', '.join(intent.host_candidates)}")
    if intent.optimization_metric:
        parts.append(f"  optimize for: {intent.optimization_metric}")
    if intent.constraints:
        parts.append(f"  constraints: {'; '.join(intent.constraints)}")
    parts.append(f"  feasibility note: {intent.feasibility_note}")
    parts.append(f"  confidence: {intent.confidence}")
    parts.append("Use this as context when answering follow-up questions.")
    return "\n".join(parts)


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest):
    """Server-sent-events stream proxying the LLM service.

    Optionally takes a DesignIntent so follow-up questions stay grounded
    in the user's current goal. Yields `data: {token|error|done}\\n\\n`
    events; the frontend consumes them via fetch + ReadableStream.
    """
    messages: list[dict] = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}]
    if req.intent is not None:
        messages.append({"role": "system", "content": _intent_context(req.intent)})
    messages.extend([m.model_dump() for m in req.messages])

    async def passthrough():
        try:
            async for chunk in llm_client.stream_chat(
                messages, temperature=req.temperature, max_tokens=req.max_tokens
            ):
                yield chunk
        except llm_client.LLMServiceError as e:
            # Best-effort error event in SSE format so the frontend can
            # show it without parsing an HTTP error after streaming began.
            import json as _json

            yield (
                f"data: {_json.dumps({'error': str(e)})}\n\n"
                f"data: {_json.dumps({'done': True})}\n\n"
            ).encode()

    return StreamingResponse(
        passthrough(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
