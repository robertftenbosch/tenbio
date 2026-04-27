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
    materialize: bool = Field(
        True,
        description=(
            "If true and the parsed intent has a kegg_id, also run the "
            "deterministic /from-compound search and return the candidate "
            "reactions. End-to-end natural-language → pathway in one call."
        ),
    )
    host: str = Field(
        "eco",
        description=(
            "KEGG organism code for materialization. Used only when "
            "materialize=true and the intent's first host_candidate "
            "doesn't map to a known KEGG organism code."
        ),
    )
    max_depth: int = Field(
        2, ge=0, le=4, description="BFS depth for materialization."
    )


class DesignFromGoalResponse(BaseModel):
    intent: DesignIntent
    candidate_kegg_count: int = Field(
        ..., description="How many KEGG candidates were pre-fetched and shown to the LLM."
    )
    candidate_uniprot_count: int
    model_used: Optional[str] = None
    pathway_candidates: Optional["PathwayCandidatesResponse"] = Field(
        None,
        description=(
            "If the parsed intent has a kegg_id and the request asked "
            "for it, the deterministic /from-compound search is run "
            "automatically and its result is included here."
        ),
    )


# --- Compound -> pathway -----------------------------------------------------


class CompoundRef(BaseModel):
    id: str = Field(..., description="KEGG compound ID, e.g. cpd:C00014")
    name: Optional[str] = None


class GeneRef(BaseModel):
    id: str = Field(..., description="KEGG gene ID, e.g. eco:b0421")
    name: Optional[str] = None
    definition: Optional[str] = None
    organism: Optional[str] = None
    ec_number: Optional[str] = None


class ReactionStep(BaseModel):
    reaction_id: str = Field(..., description="KEGG reaction ID, e.g. rn:R02749")
    reaction_name: Optional[str] = None
    equation: Optional[str] = None
    ec_numbers: list[str] = Field(default_factory=list)
    substrates: list[str] = Field(
        default_factory=list,
        description="KEGG compound IDs feeding this step (retrosynthetic upstream).",
    )
    products: list[str] = Field(
        default_factory=list,
        description="KEGG compound IDs produced by this step.",
    )
    candidate_genes: list[GeneRef] = Field(
        default_factory=list,
        description=(
            "Genes in the host organism that encode the enzyme(s) for "
            "this reaction. Empty if the host doesn't have an annotated "
            "homolog."
        ),
    )
    depth: int = Field(
        ...,
        description=(
            "BFS depth from the target. depth=0 means this reaction "
            "directly produces the target; depth=1 produces a substrate "
            "of a depth=0 reaction; etc."
        ),
    )


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class ChatStreamRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    intent: Optional["DesignIntent"] = Field(
        None,
        description=(
            "Optional DesignIntent the user is currently looking at. If "
            "set, it's prepended as a system message so follow-up "
            "questions stay grounded in the parsed goal + chassis "
            "feasibility note."
        ),
    )
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)


class DesignFromCompoundRequest(BaseModel):
    compound: str = Field(
        ...,
        description=(
            "Target compound, either a KEGG ID (cpd:C00014 or just "
            "C00014) or a free-text name to be resolved via "
            "KEGG /find/compound."
        ),
        min_length=2,
    )
    host: str = Field(
        "eco",
        description=(
            "KEGG organism code for gene lookup. Defaults to E. coli (eco)."
        ),
    )
    max_depth: int = Field(
        2,
        ge=0,
        le=4,
        description=(
            "BFS depth bound. depth=0 returns only direct producers; "
            "depth>=2 reaches grand-precursors. Capped at 4 to keep "
            "KEGG API load polite."
        ),
    )


class PathwayCandidatesResponse(BaseModel):
    target: CompoundRef
    host: str
    max_depth_used: int
    reactions: list[ReactionStep]
    notes: list[str] = Field(default_factory=list)


# Required for the forward reference in DesignFromGoalResponse and
# ChatStreamRequest (both reference types defined further down).
DesignFromGoalResponse.model_rebuild()
ChatStreamRequest.model_rebuild()
