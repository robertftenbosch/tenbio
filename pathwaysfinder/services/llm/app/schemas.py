"""Pydantic schemas for the LLM service.

The DesignIntent contract is the single most important type in this service:
it's what the goal parser produces and what the main API consumes. See
`docs/llm-service-plan.md` §6 for the full design rationale.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Goal parsing ---------------------------------------------------------


class TargetSpec(BaseModel):
    """The molecule, protein, or removal target the user wants."""

    kind: Literal["compound", "protein", "removal"] = Field(
        ...,
        description=(
            "compound = produce a small molecule; "
            "protein = produce a polypeptide; "
            "removal = consume / degrade a substance from the environment."
        ),
    )
    name: str = Field(..., description="Human-readable target name.")
    kegg_id: Optional[str] = Field(
        None,
        description=(
            "KEGG compound ID (cpd:Cxxxxx) or KO/EC reference, only when "
            "the target maps cleanly to KEGG. Must be from the candidate "
            "list provided to the LLM; null otherwise."
        ),
    )
    uniprot_id: Optional[str] = Field(
        None,
        description="UniProt accession when target is a specific protein.",
    )
    smiles: Optional[str] = Field(
        None, description="SMILES string when target is a small molecule."
    )


class GoalParseRequest(BaseModel):
    """A natural-language goal plus optional pre-fetched grounding context."""

    query: str = Field(..., description="User's natural-language goal.")
    candidate_kegg_ids: list[dict] = Field(
        default_factory=list,
        description=(
            "Pre-fetched KEGG candidates from the main API. Each item is "
            '{"id": "cpd:C00014", "name": "Ammonia", "synonyms": [...]}.'
            " The LLM picks from this list rather than inventing IDs."
        ),
    )
    candidate_uniprot_ids: list[dict] = Field(
        default_factory=list,
        description=(
            "Pre-fetched UniProt candidates. Each item is "
            '{"accession": "P02768", "name": "Albumin", "organism": "Human"}.'
        ),
    )


class DesignIntent(BaseModel):
    """Structured representation of what the user wants to build."""

    raw_query: str = Field(..., description="Original user input, preserved verbatim.")
    target: TargetSpec
    host_candidates: list[str] = Field(
        ...,
        description=(
            "Ordered list of plausible chassis organisms, most likely first. "
            "E.g. ['E. coli BL21', 'Synechocystis PCC 6803', 'P. pastoris']."
        ),
    )
    optimization_metric: Optional[
        Literal["yield", "rate", "titer", "robustness"]
    ] = Field(
        None,
        description=(
            "What to optimize for. yield = product per substrate; "
            "rate = product per time; titer = concentration; "
            "robustness = stability under stress."
        ),
    )
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "Hard or soft constraints from the goal, free text. "
            "E.g. 'must use sunlight', 'open-environment release', "
            "'food-grade only'."
        ),
    )
    feasibility_note: str = Field(
        ...,
        description=(
            "Honest assessment of whether the request is biologically "
            "realistic, mentioning known showstoppers (glycosylation, "
            "PTMs, growth rate, etc.). Always populated."
        ),
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ...,
        description=(
            "Parser confidence. low = ambiguous query or research-grade "
            "biology; high = well-known chassis + target."
        ),
    )


class GoalParseResponse(BaseModel):
    intent: DesignIntent
    model_used: str = Field(..., description="Actual model name that produced this.")
    raw_llm_output: Optional[str] = Field(
        None,
        description=(
            "Raw text from the LLM before JSON parsing. Useful for "
            "debugging when intent fields look wrong."
        ),
    )


# --- Chat -----------------------------------------------------------------


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    temperature: float = Field(0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)


class ChatResponse(BaseModel):
    content: str
    model_used: str


# --- Health ---------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str
    ollama_reachable: bool
