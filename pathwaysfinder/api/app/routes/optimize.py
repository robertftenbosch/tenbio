"""API endpoints for sequence optimization."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.services.codon_optimizer import (
    optimize_protein_sequence,
    optimize_dna_sequence,
    translate_dna,
)

router = APIRouter(prefix="/api/v1/optimize", tags=["optimization"])


class ProteinOptimizeRequest(BaseModel):
    sequence: str = Field(..., description="Protein sequence (amino acids)")
    organism: Literal["ecoli", "yeast"] = Field(default="ecoli", description="Target organism")
    strategy: Literal["most_frequent", "weighted"] = Field(
        default="most_frequent",
        description="Optimization strategy"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sequence": "MVSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTLTYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITLGMDELYK",
                "organism": "ecoli",
                "strategy": "most_frequent"
            }
        }


class DNAOptimizeRequest(BaseModel):
    sequence: str = Field(..., description="DNA sequence to optimize")
    organism: Literal["ecoli", "yeast"] = Field(default="ecoli", description="Target organism")
    strategy: Literal["most_frequent", "weighted"] = Field(
        default="most_frequent",
        description="Optimization strategy"
    )


class TranslateRequest(BaseModel):
    sequence: str = Field(..., description="DNA sequence to translate")


class OptimizeResponse(BaseModel):
    original_protein: str
    optimized_dna: str
    organism: str
    strategy: str
    length_bp: int
    length_aa: int
    gc_content: float
    original_dna: str | None = None
    original_length_bp: int | None = None
    codons_changed: int | None = None
    codons_unchanged: int | None = None


class TranslateResponse(BaseModel):
    dna_sequence: str
    protein_sequence: str
    length_bp: int
    length_aa: int


@router.post("/protein", response_model=OptimizeResponse)
def optimize_protein(request: ProteinOptimizeRequest):
    """
    Optimize a protein sequence for expression in a target organism.

    Takes an amino acid sequence and returns a codon-optimized DNA sequence.
    """
    try:
        result = optimize_protein_sequence(
            protein_sequence=request.sequence,
            organism=request.organism,
            strategy=request.strategy,
        )
        return OptimizeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/dna", response_model=OptimizeResponse)
def optimize_dna(request: DNAOptimizeRequest):
    """
    Re-optimize an existing DNA sequence for a different organism.

    Translates the DNA to protein, then optimizes codons for the target organism.
    """
    try:
        result = optimize_dna_sequence(
            dna_sequence=request.sequence,
            organism=request.organism,
            strategy=request.strategy,
        )
        return OptimizeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/translate", response_model=TranslateResponse)
def translate(request: TranslateRequest):
    """
    Translate a DNA sequence to protein.
    """
    try:
        dna = request.sequence.upper().replace(" ", "").replace("\n", "")
        protein = translate_dna(dna)

        if not protein:
            raise ValueError("Could not translate sequence - no valid codons found")

        return TranslateResponse(
            dna_sequence=dna,
            protein_sequence=protein,
            length_bp=len(dna),
            length_aa=len(protein),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
