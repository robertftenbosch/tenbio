"""Pydantic models for the Protenix prediction service."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChainInput(BaseModel):
    """A single chain/entity in a prediction request."""

    type: Literal["protein", "dna", "rna", "ligand", "ion"] = Field(
        ..., description="Type of biomolecular chain"
    )
    sequence: Optional[str] = Field(
        None, description="Amino acid or nucleotide sequence"
    )
    ligand_id: Optional[str] = Field(
        None, description="CCD code (e.g. ATP) or SMILES string for ligands"
    )
    ion_id: Optional[str] = Field(None, description="Ion identifier (e.g. MG, ZN)")
    count: int = Field(1, description="Number of copies of this chain", ge=1)


class PredictionRequest(BaseModel):
    """Request to submit a structure prediction job."""

    name: str = Field("prediction", description="Job name")
    sequences: list[ChainInput] = Field(
        ..., description="List of chains to predict", min_length=1
    )
    model_name: str = Field(
        "protenix_base_default_v1.0.0", description="Protenix model name"
    )
    num_seeds: int = Field(1, description="Number of random seeds", ge=1, le=10)
    num_samples: int = Field(5, description="Number of diffusion samples", ge=1, le=20)


class ConfidenceScores(BaseModel):
    """Confidence metrics for a prediction."""

    plddt: Optional[float] = Field(None, description="Predicted lDDT score (0-100)")
    ptm: Optional[float] = Field(None, description="Predicted TM-score (0-1)")
    iptm: Optional[float] = Field(None, description="Interface pTM score (0-1)")
    ranking_score: Optional[float] = Field(None, description="Overall ranking score")


class JobStatus(BaseModel):
    """Status of a prediction job."""

    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    confidence: Optional[ConfidenceScores] = None
    structure_available: bool = False


class ModelInfo(BaseModel):
    """Metadata for a Protenix model variant."""

    name: str
    description: str
    parameters_m: float = Field(description="Model parameters in millions")
    features: list[str] = Field(description="Supported features (MSA, Template, ESM, etc.)")
    speed_tier: Literal["fast", "medium", "slow"] = Field(
        description="Relative speed tier"
    )
    default: bool = False
    loaded: bool = False


class PreloadRequest(BaseModel):
    """Request to preload a model into GPU memory."""

    model_name: str = Field(..., description="Protenix model name to preload")


class PreloadResponse(BaseModel):
    """Response from a model preload request."""

    model_name: str
    status: Literal["loading", "already_loaded", "error"]
    message: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    gpu_available: bool
    gpu_name: Optional[str] = None
    model_loaded: bool
    loaded_model: Optional[str] = None
