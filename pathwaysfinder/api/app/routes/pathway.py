"""CRUD routes for Pathway objects.

Pathways are ordered assemblies of Parts, representing the genetic constructs
you want to build in the lab (e.g. pBbA5c-MevT-MBIS for bisabolene POC).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from app.database import get_db
from app.models.pathway import Pathway, PathwayPart
from app.models.parts import Part
from app.schemas.pathway import (
    PathwayCreate, PathwayUpdate,
    PathwayResponse, PathwayPartResponse,
    PathwayListResponse, PathwayListItem,
)
from app.services.pathway_export import pathway_to_genbank, pathway_to_fasta


router = APIRouter(prefix="/api/v1/pathways", tags=["pathways"])


# ------------------------- helpers -------------------------

def _attach_part_summaries(pathway: Pathway) -> PathwayResponse:
    """Build a PathwayResponse with denormalized part name/type + total length."""
    parts_out: list[PathwayPartResponse] = []
    total_len = 0
    for pp in pathway.pathway_parts:
        parts_out.append(PathwayPartResponse(
            id=pp.id,
            part_id=pp.part_id,
            position=pp.position,
            direction=pp.direction,
            notes=pp.notes,
            part_name=pp.part.name if pp.part else None,
            part_type=pp.part.type if pp.part else None,
        ))
        if pp.part and pp.part.sequence:
            total_len += len(pp.part.sequence)

    return PathwayResponse(
        id=pathway.id,
        name=pathway.name,
        description=pathway.description,
        host_organism=pathway.host_organism,
        plasmid_backbone=pathway.plasmid_backbone,
        selection_marker=pathway.selection_marker,
        target_molecule=pathway.target_molecule,
        source=pathway.source,
        reference_doi=pathway.reference_doi,
        notes=pathway.notes,
        created_at=pathway.created_at,
        updated_at=pathway.updated_at,
        parts=parts_out,
        assembled_length_bp=total_len or None,
    )


def _validate_parts_exist(db: Session, part_ids: list[str]) -> None:
    """Raise 400 if any part_id does not correspond to an existing Part."""
    if not part_ids:
        return
    found = {p.id for p in db.query(Part.id).filter(Part.id.in_(part_ids)).all()}
    missing = [pid for pid in part_ids if pid not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown part_id(s): {missing}",
        )


# ------------------------- CRUD -------------------------

@router.get("", response_model=PathwayListResponse)
def list_pathways(
    host_organism: str | None = Query(None),
    target_molecule: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Pathway).options(selectinload(Pathway.pathway_parts))

    if host_organism:
        query = query.filter(Pathway.host_organism == host_organism)
    if target_molecule:
        query = query.filter(Pathway.target_molecule == target_molecule)
    if search:
        query = query.filter(
            or_(
                Pathway.name.ilike(f"%{search}%"),
                Pathway.description.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    rows = query.order_by(Pathway.created_at.desc()).offset(skip).limit(limit).all()

    items = [
        PathwayListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            host_organism=p.host_organism,
            target_molecule=p.target_molecule,
            part_count=len(p.pathway_parts),
            created_at=p.created_at,
        )
        for p in rows
    ]
    return PathwayListResponse(pathways=items, total=total)


@router.get("/{pathway_id}", response_model=PathwayResponse)
def get_pathway(pathway_id: str, db: Session = Depends(get_db)):
    pathway = (
        db.query(Pathway)
        .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
        .filter(Pathway.id == pathway_id)
        .first()
    )
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")
    return _attach_part_summaries(pathway)


@router.post("", response_model=PathwayResponse, status_code=201)
def create_pathway(payload: PathwayCreate, db: Session = Depends(get_db)):
    # Reject duplicate names
    if db.query(Pathway).filter(Pathway.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Pathway with this name already exists")

    # Reject duplicate positions in payload
    positions = [p.position for p in payload.parts]
    if len(positions) != len(set(positions)):
        raise HTTPException(status_code=400, detail="Duplicate positions in parts list")

    _validate_parts_exist(db, [p.part_id for p in payload.parts])

    pathway = Pathway(
        name=payload.name,
        description=payload.description,
        host_organism=payload.host_organism,
        plasmid_backbone=payload.plasmid_backbone,
        selection_marker=payload.selection_marker,
        target_molecule=payload.target_molecule,
        source=payload.source,
        reference_doi=payload.reference_doi,
        notes=payload.notes,
    )
    for pp in payload.parts:
        pathway.pathway_parts.append(PathwayPart(
            part_id=pp.part_id,
            position=pp.position,
            direction=pp.direction,
            notes=pp.notes,
        ))

    db.add(pathway)
    db.commit()
    db.refresh(pathway)
    # Reload with joinedload to populate part_name/part_type
    pathway = (
        db.query(Pathway)
        .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
        .filter(Pathway.id == pathway.id)
        .first()
    )
    return _attach_part_summaries(pathway)


@router.put("/{pathway_id}", response_model=PathwayResponse)
def update_pathway(pathway_id: str, payload: PathwayUpdate, db: Session = Depends(get_db)):
    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")

    if payload.name and payload.name != pathway.name:
        if db.query(Pathway).filter(Pathway.name == payload.name).first():
            raise HTTPException(status_code=400, detail="Pathway with this name already exists")

    # Update scalar fields
    update_data = payload.model_dump(exclude_unset=True, exclude={"parts"})
    for field, value in update_data.items():
        setattr(pathway, field, value)

    # Replace parts list if provided
    if payload.parts is not None:
        positions = [p.position for p in payload.parts]
        if len(positions) != len(set(positions)):
            raise HTTPException(status_code=400, detail="Duplicate positions in parts list")
        _validate_parts_exist(db, [p.part_id for p in payload.parts])

        # Orphan-delete existing children
        pathway.pathway_parts.clear()
        db.flush()
        for pp in payload.parts:
            pathway.pathway_parts.append(PathwayPart(
                part_id=pp.part_id,
                position=pp.position,
                direction=pp.direction,
                notes=pp.notes,
            ))

    db.commit()
    db.refresh(pathway)
    pathway = (
        db.query(Pathway)
        .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
        .filter(Pathway.id == pathway.id)
        .first()
    )
    return _attach_part_summaries(pathway)


@router.delete("/{pathway_id}", status_code=204)
def delete_pathway(pathway_id: str, db: Session = Depends(get_db)):
    pathway = db.query(Pathway).filter(Pathway.id == pathway_id).first()
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")
    db.delete(pathway)
    db.commit()
    return None


# ------------------------- Export endpoints -------------------------

@router.get("/{pathway_id}/export/genbank")
def export_genbank(pathway_id: str, db: Session = Depends(get_db)):
    pathway = (
        db.query(Pathway)
        .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
        .filter(Pathway.id == pathway_id)
        .first()
    )
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")

    gb_text = pathway_to_genbank(pathway)
    return Response(
        content=gb_text,
        media_type="text/x-genbank",
        headers={"Content-Disposition": f'attachment; filename="{pathway.name}.gb"'},
    )


@router.get("/{pathway_id}/export/fasta")
def export_fasta(pathway_id: str, db: Session = Depends(get_db)):
    pathway = (
        db.query(Pathway)
        .options(selectinload(Pathway.pathway_parts).selectinload(PathwayPart.part))
        .filter(Pathway.id == pathway_id)
        .first()
    )
    if not pathway:
        raise HTTPException(status_code=404, detail="Pathway not found")

    fa_text = pathway_to_fasta(pathway)
    return Response(
        content=fa_text,
        media_type="text/x-fasta",
        headers={"Content-Disposition": f'attachment; filename="{pathway.name}.fasta"'},
    )
