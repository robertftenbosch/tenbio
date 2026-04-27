"""Primer design endpoints.

Two entry points:
    POST /api/v1/primers/gibson               raw fragments in the request body
    POST /api/v1/primers/gibson/from-pathway  uses an existing Pathway (PR1)

The pathway-based endpoint is optional and only works if PR1 is merged.
It is gated behind an import-guard so this route module still loads cleanly
if the Pathway model is not yet present.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.primer_design import design_gibson_primers
from app.schemas.primer import (
    PrimerDesignRequest, PrimerDesignResponse,
    PrimerPairResponse, PathwayPrimerRequest,
)


router = APIRouter(prefix="/api/v1/primers", tags=["primers"])


def _to_response(result) -> PrimerDesignResponse:
    pairs = [
        PrimerPairResponse(
            fragment_index=p.fragment_index,
            fragment_name=p.fragment_name,
            forward_primer=p.forward_primer,
            reverse_primer=p.reverse_primer,
            forward_anneal=p.forward_anneal,
            reverse_anneal=p.reverse_anneal,
            forward_overhang=p.forward_overhang,
            reverse_overhang=p.reverse_overhang,
            forward_tm=p.forward_tm,
            reverse_tm=p.reverse_tm,
            forward_gc=p.forward_gc,
            reverse_gc=p.reverse_gc,
            forward_length=len(p.forward_primer),
            reverse_length=len(p.reverse_primer),
            warnings=p.warnings,
        )
        for p in result.primer_pairs
    ]
    return PrimerDesignResponse(
        primer_pairs=pairs,
        global_warnings=result.global_warnings,
    )


@router.post("/gibson", response_model=PrimerDesignResponse)
def design_primers(payload: PrimerDesignRequest):
    """Design Gibson Assembly primers for an ordered list of fragments."""
    try:
        result = design_gibson_primers(
            fragments=[f.model_dump() for f in payload.fragments],
            circular=payload.circular,
            overlap_bp=payload.overlap_bp,
            target_tm=payload.target_tm,
            tm_tolerance=payload.tm_tolerance,
            min_anneal_bp=payload.min_anneal_bp,
            max_anneal_bp=payload.max_anneal_bp,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_response(result)


# --- Pathway-based endpoint (requires PR1) --------------------------------

try:
    from app.models.pathway import Pathway, PathwayPart  # noqa: F401
    _PATHWAY_MODEL_AVAILABLE = True
except ImportError:
    _PATHWAY_MODEL_AVAILABLE = False


if _PATHWAY_MODEL_AVAILABLE:

    from sqlalchemy.orm import selectinload

    @router.post("/gibson/from-pathway", response_model=PrimerDesignResponse)
    def design_primers_from_pathway(
        payload: PathwayPrimerRequest,
        db: Session = Depends(get_db),
    ):
        """Design primers for the fragments of an existing Pathway.

        Each part in the pathway becomes one Gibson fragment, in position order.
        For finer control, use POST /api/v1/primers/gibson with custom fragments.
        """
        pathway = (
            db.query(Pathway)
            .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
            .filter(Pathway.id == payload.pathway_id)
            .first()
        )
        if not pathway:
            raise HTTPException(status_code=404, detail="Pathway not found")

        ordered = sorted(pathway.pathway_parts, key=lambda pp: pp.position)
        fragments = []
        for pp in ordered:
            if not pp.part or not pp.part.sequence:
                continue
            fragments.append({
                "name": pp.part.name,
                "sequence": pp.part.sequence,
            })

        if len(fragments) < 2:
            raise HTTPException(
                status_code=400,
                detail="Pathway must contain at least 2 parts with sequences",
            )

        try:
            result = design_gibson_primers(
                fragments=fragments,
                circular=payload.circular,
                overlap_bp=payload.overlap_bp,
                target_tm=payload.target_tm,
                tm_tolerance=payload.tm_tolerance,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return _to_response(result)
