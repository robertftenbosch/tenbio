"""Simulation routes — Flux Balance Analysis and (later) strain optimization.

This module is the deterministic counterpart to /api/v1/design/from-goal:
once the user has a candidate pathway, FBA tells them whether it could
actually run in the chosen chassis and at what predicted rate.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.fba import (
    ChassisInfo,
    FBARequest,
    FBAResponse,
    FluxEntry,
)
from app.services import fba

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/simulate", tags=["simulation"])


@router.get("/chassis", response_model=list[ChassisInfo])
def list_chassis_models() -> list[dict]:
    """List the genome-scale models the FBA endpoint can run against."""
    return fba.list_chassis()


@router.post("/fba", response_model=FBAResponse)
def run_fba(req: FBARequest) -> FBAResponse:
    """Run Flux Balance Analysis on the requested chassis.

    Synchronous — `textbook` solves in milliseconds. Larger models
    (iML1515 etc.) take ~100 ms per call; we will move them behind the
    PredictionJob queue if/when latency becomes an issue.
    """
    if req.objective == "target" and not req.target_reaction:
        raise HTTPException(
            status_code=422,
            detail="objective='target' requires target_reaction.",
        )
    try:
        result = fba.run_fba(
            req.chassis,
            target_reaction=req.target_reaction,
            knockouts=req.knockouts,
            objective=req.objective,
            carbon_source=req.carbon_source,
            carbon_uptake=req.carbon_uptake,
            flux_limit=req.flux_limit,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:  # pragma: no cover - safety net for solver oddities
        logger.exception("FBA solver failed unexpectedly")
        raise HTTPException(status_code=500, detail=f"FBA solver error: {e}")

    return FBAResponse(
        chassis=result.chassis,
        objective_id=result.objective_id,
        objective_value=result.objective_value,
        growth_rate=result.growth_rate,
        target_reaction=result.target_reaction,
        target_flux=result.target_flux,
        status=result.status,
        fluxes=[FluxEntry(**f) for f in result.fluxes],
        notes=result.notes,
    )
