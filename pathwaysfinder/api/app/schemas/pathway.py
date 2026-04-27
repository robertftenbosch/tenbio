"""Pydantic schemas for Pathway and PathwayPart."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


# ------------------------- PathwayPart (embedded) -------------------------

class PathwayPartBase(BaseModel):
    part_id: str
    position: int = Field(ge=0)
    direction: Literal["forward", "reverse"] = "forward"
    notes: str | None = None


class PathwayPartCreate(PathwayPartBase):
    pass


class PathwayPartResponse(PathwayPartBase):
    id: str
    # Denormalized part summary for convenient frontend rendering
    part_name: str | None = None
    part_type: str | None = None

    class Config:
        from_attributes = True


# ------------------------- Pathway -------------------------

class PathwayBase(BaseModel):
    name: str
    description: str | None = None
    host_organism: str | None = None
    plasmid_backbone: str | None = None
    selection_marker: str | None = None
    target_molecule: str | None = None
    source: str | None = None
    reference_doi: str | None = None
    notes: str | None = None


class PathwayCreate(PathwayBase):
    parts: list[PathwayPartCreate] = Field(default_factory=list)


class PathwayUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    host_organism: str | None = None
    plasmid_backbone: str | None = None
    selection_marker: str | None = None
    target_molecule: str | None = None
    source: str | None = None
    reference_doi: str | None = None
    notes: str | None = None
    # If parts is provided, the full ordered list is REPLACED.
    parts: list[PathwayPartCreate] | None = None


class PathwayResponse(PathwayBase):
    id: str
    created_at: datetime
    updated_at: datetime | None = None
    parts: list[PathwayPartResponse] = Field(default_factory=list)
    assembled_length_bp: int | None = None  # sum of part sequence lengths

    class Config:
        from_attributes = True


class PathwayListItem(BaseModel):
    """Lightweight listing view (no parts)."""
    id: str
    name: str
    description: str | None = None
    host_organism: str | None = None
    target_molecule: str | None = None
    part_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class PathwayListResponse(BaseModel):
    pathways: list[PathwayListItem]
    total: int
