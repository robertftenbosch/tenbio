from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.parts import Part
from app.schemas.parts import PartResponse, PartListResponse, PartCreate, PartUpdate, PapersListResponse
from app.external_apis.pubmed import search_papers_for_part

router = APIRouter(prefix="/api/v1/parts", tags=["parts"])


@router.get("", response_model=PartListResponse)
def list_parts(
    type: str | None = Query(None, description="Filter by part type"),
    organism: str | None = Query(None, description="Filter by organism"),
    search: str | None = Query(None, description="Search in name and description"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Part)

    if type:
        query = query.filter(Part.type == type)
    if organism:
        query = query.filter(Part.organism == organism)
    if search:
        query = query.filter(
            or_(
                Part.name.ilike(f"%{search}%"),
                Part.description.ilike(f"%{search}%"),
            )
        )

    total = query.count()
    parts = query.offset(skip).limit(limit).all()

    return PartListResponse(parts=parts, total=total)


@router.get("/{part_id}", response_model=PartResponse)
def get_part(part_id: str, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


@router.post("", response_model=PartResponse, status_code=201)
def create_part(part: PartCreate, db: Session = Depends(get_db)):
    existing = db.query(Part).filter(Part.name == part.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Part with this name already exists")

    db_part = Part(**part.model_dump())
    db.add(db_part)
    db.commit()
    db.refresh(db_part)
    return db_part


@router.put("/{part_id}", response_model=PartResponse)
def update_part(part_id: str, part_update: PartUpdate, db: Session = Depends(get_db)):
    db_part = db.query(Part).filter(Part.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Check for name conflict if name is being updated
    if part_update.name and part_update.name != db_part.name:
        existing = db.query(Part).filter(Part.name == part_update.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Part with this name already exists")

    # Update only provided fields
    update_data = part_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_part, field, value)

    db.commit()
    db.refresh(db_part)
    return db_part


@router.delete("/{part_id}", status_code=204)
def delete_part(part_id: str, db: Session = Depends(get_db)):
    db_part = db.query(Part).filter(Part.id == part_id).first()
    if not db_part:
        raise HTTPException(status_code=404, detail="Part not found")

    db.delete(db_part)
    db.commit()
    return None


@router.get("/{part_id}/papers", response_model=PapersListResponse)
async def get_part_papers(part_id: str, db: Session = Depends(get_db)):
    """Fetch related research papers for a part from PubMed."""
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    papers = await search_papers_for_part(
        part_name=part.name,
        part_type=part.type,
        description=part.description,
    )

    return PapersListResponse(papers=papers, query=part.name)
