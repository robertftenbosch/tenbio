"""Pydantic schemas for /api/v1/simulate/fba."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FBARequest(BaseModel):
    chassis: str = Field(
        "textbook",
        description=(
            "Genome-scale model key from /api/v1/simulate/chassis. v1 ships "
            "with 'textbook' (E. coli core, ~95 reactions); larger models "
            "land via Phase 3."
        ),
    )
    objective: Literal["biomass", "target"] = Field(
        "biomass",
        description=(
            "What the LP maximises. 'biomass' uses the model's bundled "
            "biomass reaction; 'target' requires a target_reaction id."
        ),
    )
    target_reaction: Optional[str] = Field(
        None,
        description=(
            "Reaction to maximise when objective='target', e.g. an exchange "
            "for the product of interest like 'EX_etoh_e'."
        ),
    )
    knockouts: list[str] = Field(
        default_factory=list,
        description="Reaction IDs to knock out (set bounds=0,0).",
    )
    carbon_source: Optional[str] = Field(
        None,
        description=(
            "Override the default carbon source, e.g. 'EX_glc__D_e' for "
            "glucose. Other carbon-source exchanges are closed."
        ),
    )
    carbon_uptake: float = Field(
        -10.0,
        description=(
            "Lower bound of the chosen carbon-source exchange. Negative "
            "= consumption per cobra convention."
        ),
    )
    flux_limit: int = Field(
        25,
        ge=1,
        le=200,
        description="Top-N reactions by |flux| to include in the response.",
    )


class FluxEntry(BaseModel):
    reaction_id: str
    flux: float
    lower_bound: float
    upper_bound: float
    name: Optional[str] = None


class FBAResponse(BaseModel):
    chassis: str
    objective_id: str
    objective_value: float
    growth_rate: float
    target_reaction: Optional[str]
    target_flux: Optional[float]
    status: str
    fluxes: list[FluxEntry]
    notes: list[str]


class ChassisInfo(BaseModel):
    key: str
    description: str
    organism: str
    kegg_organism: str
    domain: Literal["bacterial", "fungal", "photosynthetic", "mammalian"]
    n_reactions: int
    biomass_objective: str
