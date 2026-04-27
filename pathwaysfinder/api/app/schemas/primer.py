"""Pydantic schemas for Gibson primer design."""

from pydantic import BaseModel, Field


class FragmentInput(BaseModel):
    name: str
    sequence: str = Field(min_length=50, description="DNA sequence (ACGTN)")


class PrimerDesignRequest(BaseModel):
    fragments: list[FragmentInput] = Field(min_length=2)
    circular: bool = Field(False, description="True for plasmid (loop), False for linear product")
    overlap_bp: int = Field(25, ge=15, le=50, description="Homology overlap length")
    target_tm: float = Field(60.0, ge=50.0, le=72.0, description="Target Tm of annealing region (Celsius)")
    tm_tolerance: float = Field(3.0, ge=1.0, le=10.0)
    min_anneal_bp: int = Field(18, ge=15, le=40)
    max_anneal_bp: int = Field(35, ge=20, le=50)


class PrimerPairResponse(BaseModel):
    fragment_index: int
    fragment_name: str
    forward_primer: str
    reverse_primer: str
    forward_anneal: str
    reverse_anneal: str
    forward_overhang: str
    reverse_overhang: str
    forward_tm: float
    reverse_tm: float
    forward_gc: float
    reverse_gc: float
    forward_length: int
    reverse_length: int
    warnings: list[str] = []


class PrimerDesignResponse(BaseModel):
    primer_pairs: list[PrimerPairResponse]
    global_warnings: list[str] = []
    order_format: str = Field(
        "IDT / Eurofins compatible: 5' -> 3', standard salt-free desalting is fine for Gibson."
    )


# Request schema for pathway-based design (uses pathway_id instead of raw fragments)
class PathwayPrimerRequest(BaseModel):
    pathway_id: str
    circular: bool = False
    overlap_bp: int = 25
    target_tm: float = 60.0
    tm_tolerance: float = 3.0
