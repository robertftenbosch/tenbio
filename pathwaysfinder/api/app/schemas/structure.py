"""Pydantic schemas for structure prediction API."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChainInput(BaseModel):
    """A single biomolecular chain for structure prediction."""

    type: Literal["protein", "dna", "rna", "ligand", "ion"] = Field(
        ..., description="Type of chain"
    )
    sequence: Optional[str] = Field(
        None, description="Amino acid or nucleotide sequence"
    )
    ligand_id: Optional[str] = Field(
        None, description="CCD code (e.g. ATP) or SMILES string"
    )
    ion_id: Optional[str] = Field(None, description="Ion identifier (e.g. MG, ZN)")
    count: int = Field(1, description="Number of copies", ge=1)


class StructurePredictRequest(BaseModel):
    """Request to predict a biomolecular structure."""

    name: str = Field("prediction", description="Prediction job name")
    chains: list[ChainInput] = Field(
        ..., description="List of chains to predict", min_length=1
    )
    model_name: str = Field(
        "protenix_base_default_v1.0.0", description="Model variant"
    )
    num_samples: int = Field(5, description="Number of diffusion samples", ge=1, le=20)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "GFP structure",
                "chains": [
                    {
                        "type": "protein",
                        "sequence": "MVSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTLTYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITLGMDELYK",
                        "count": 1,
                    }
                ],
                "model_name": "protenix_base_default_v1.0.0",
                "num_samples": 5,
            }
        }

    @classmethod
    def from_protein_sequence(cls, name: str, sequence: str) -> "StructurePredictRequest":
        """Convenience constructor for a single protein prediction."""
        return cls(
            name=name,
            chains=[ChainInput(type="protein", sequence=sequence)],
        )


class ConfidenceScores(BaseModel):
    """Confidence metrics from structure prediction."""

    plddt: Optional[float] = None
    ptm: Optional[float] = None
    iptm: Optional[float] = None
    ranking_score: Optional[float] = None


class StructurePredictResponse(BaseModel):
    """Response after submitting a prediction job."""

    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Detailed status of a prediction job."""

    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    confidence: Optional[ConfidenceScores] = None
    structure_available: bool = False
