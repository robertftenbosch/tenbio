"""Design routes — natural-language and compound-driven pathway design.

This PR ships only `/from-goal` (LLM-driven). The deterministic
`/from-compound` (KEGG reverse pathway search) lands in the next PR;
this file leaves a stub so the URL is reserved.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.external_apis import llm_client
from app.schemas.design import (
    DesignFromGoalRequest,
    DesignFromGoalResponse,
    DesignIntent,
)
from app.services import goal_grounding

router = APIRouter(prefix="/api/v1/design", tags=["design"])


@router.post("/from-goal", response_model=DesignFromGoalResponse)
async def design_from_goal(req: DesignFromGoalRequest):
    """Translate a natural-language goal into a structured DesignIntent.

    Pre-LLM grounding step: extract probable target keywords from the
    query, search KEGG (compounds) and UniProt (proteins), and pass the
    candidate IDs to the LLM. The LLM is instructed to only use IDs from
    that list; any IDs that escape are stripped on the LLM-service side.

    The next PR (`/from-compound`) will take the parsed intent and
    produce a candidate Pathway via KEGG reverse search. For now we just
    return the intent.
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
    return DesignFromGoalResponse(
        intent=intent,
        candidate_kegg_count=len(kegg_candidates),
        candidate_uniprot_count=len(uniprot_candidates),
        model_used=result.get("model_used"),
    )


@router.post("/from-compound")
async def design_from_compound():
    """Reserved for the deterministic KEGG reverse pathway search (next PR)."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Not yet implemented. Will land in the follow-up PR; tracked "
            "in TODO.md Phase 1. Use POST /api/v1/design/from-goal for "
            "now (LLM-driven)."
        ),
    )
