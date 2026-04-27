"""Pathway and PathwayPart models for representing genetic constructs.

A Pathway is an ordered assembly of Parts (promoter, RBS, gene, terminator, ...)
targeted at a specific host organism, optionally on a named plasmid backbone.
This is the core object you build, version, and export to GenBank/SBOL.
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Pathway(Base):
    __tablename__ = "pathways"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Design metadata
    host_organism = Column(String(50), nullable=True, index=True)   # ecoli, yeast, ...
    plasmid_backbone = Column(String(100), nullable=True)           # pBbA5c, pTrc99A, ...
    selection_marker = Column(String(50), nullable=True)            # carbenicillin, chloramphenicol, ...
    target_molecule = Column(String(100), nullable=True, index=True)  # bisabolene, limonene, ...

    # Provenance
    source = Column(String(100), nullable=True)        # "Addgene 35152", "custom", ...
    reference_doi = Column(String(200), nullable=True)  # DOI of origin paper, if any
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Ordered list of parts (via association table)
    pathway_parts = relationship(
        "PathwayPart",
        back_populates="pathway",
        cascade="all, delete-orphan",
        order_by="PathwayPart.position",
    )


class PathwayPart(Base):
    """Association between a Pathway and a Part, carrying assembly order + optional overrides.

    We keep this as a real model (not a plain association table) so we can
    track position, direction and per-instance notes — important for
    multi-cassette operons where the same Part (e.g. a terminator) appears
    several times in one Pathway.
    """
    __tablename__ = "pathway_parts"
    __table_args__ = (
        UniqueConstraint("pathway_id", "position", name="uq_pathway_position"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pathway_id = Column(String(36), ForeignKey("pathways.id", ondelete="CASCADE"), nullable=False, index=True)
    part_id = Column(String(36), ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True)

    position = Column(Integer, nullable=False)          # 0-based assembly order
    direction = Column(String(8), nullable=False, default="forward")  # forward | reverse
    notes = Column(Text, nullable=True)                 # e.g. "codon-optimized", "silent mutation at bp 453"

    pathway = relationship("Pathway", back_populates="pathway_parts")
    part = relationship("Part")  # no back_populates to avoid circular burden on Part model
