"""Pydantic schemas for the /api/v1/design endpoints.

These mirror the LLM service's DesignIntent so the main API can validate
the response before handing it to the frontend. Keeping a separate copy
(rather than importing from the LLM service) means the API doesn't
depend on the LLM service code directory.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class TargetSpec(BaseModel):
    kind: Literal["compound", "protein", "removal"]
    name: str
    kegg_id: Optional[str] = None
    uniprot_id: Optional[str] = None
    smiles: Optional[str] = None


class DesignIntent(BaseModel):
    raw_query: str
    target: TargetSpec
    host_candidates: list[str]
    optimization_metric: Optional[
        Literal["yield", "rate", "titer", "robustness"]
    ] = None
    constraints: list[str] = Field(default_factory=list)
    feasibility_note: str
    confidence: Literal["high", "medium", "low"]


class DesignFromGoalRequest(BaseModel):
    query: str = Field(
        ..., description="Natural-language goal, e.g. 'maak een organisme dat ammoniak afbreekt'.", min_length=3
    )
    skip_grounding: bool = Field(
        False,
        description=(
            "If true, send the goal to the LLM without pre-fetching KEGG/"
            "UniProt candidates. Faster but the LLM may produce IDs that "
            "get nulled out. Default false."
        ),
    )


class DesignFromGoalResponse(BaseModel):
    intent: DesignIntent
    candidate_kegg_count: int = Field(
        ..., description="How many KEGG candidates were pre-fetched and shown to the LLM."
    )
    candidate_uniprot_count: int
    model_used: Optional[str] = None
