"""iGEM Registry API routes for fetching BioBrick parts."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.parts import Part
from app.external_apis.igem import fetch_igem_part, search_igem_parts, fetch_popular_parts

router = APIRouter(prefix="/api/v1/igem", tags=["iGEM Registry"])


class IgemPartResponse(BaseModel):
    name: str
    type: str
    description: str | None = None
    sequence: str
    organism: str | None = None
    source: str = "iGEM"


class IgemPartsListResponse(BaseModel):
    parts: list[IgemPartResponse]
    total: int


class ImportResult(BaseModel):
    success: bool
    message: str
    part: IgemPartResponse | None = None


@router.get("/part/{part_name}", response_model=IgemPartResponse)
async def get_igem_part(part_name: str):
    """
    Fetch a specific part from the iGEM Registry by name.

    Example: /api/v1/igem/part/BBa_J23100
    """
    part = await fetch_igem_part(part_name)
    if not part:
        raise HTTPException(status_code=404, detail=f"Part {part_name} not found in iGEM Registry")
    return part


@router.get("/search", response_model=IgemPartsListResponse)
async def search_igem(
    type: str | None = Query(None, description="Part type: promoter, rbs, terminator, gene"),
    q: str | None = Query(None, description="Search term"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Search for parts in the iGEM Registry.

    Note: This searches live in the iGEM database, which may be slower than local search.
    """
    parts = await search_igem_parts(part_type=type, search_term=q, max_results=limit)
    return IgemPartsListResponse(parts=parts, total=len(parts))


@router.get("/popular", response_model=IgemPartsListResponse)
async def get_popular_parts(
    type: str | None = Query(None, description="Part type: promoter, rbs, terminator, gene"),
    limit: int = Query(10, ge=1, le=20),
):
    """
    Get popular/commonly used parts from iGEM Registry.

    Returns a curated list of well-characterized, widely-used parts.
    """
    parts = await fetch_popular_parts(category=type, limit=limit)
    return IgemPartsListResponse(parts=parts, total=len(parts))


@router.post("/import/{part_name}", response_model=ImportResult)
async def import_igem_part(
    part_name: str,
    db: Session = Depends(get_db),
):
    """
    Import a part from iGEM Registry into the local database.

    Fetches the part from iGEM and saves it locally for use in pathway design.
    """
    # Check if already exists
    existing = db.query(Part).filter(Part.name == part_name).first()
    if existing:
        return ImportResult(
            success=False,
            message=f"Part {part_name} already exists in local database",
            part=None
        )

    # Fetch from iGEM
    igem_part = await fetch_igem_part(part_name)
    if not igem_part:
        raise HTTPException(
            status_code=404,
            detail=f"Part {part_name} not found in iGEM Registry"
        )

    # Create local part
    db_part = Part(
        name=igem_part["name"],
        type=igem_part["type"],
        description=igem_part.get("description"),
        sequence=igem_part["sequence"],
        organism=igem_part.get("organism"),
        source="iGEM",
    )
    db.add(db_part)
    db.commit()
    db.refresh(db_part)

    return ImportResult(
        success=True,
        message=f"Successfully imported {part_name} from iGEM Registry",
        part=igem_part
    )


@router.post("/import-batch", response_model=list[ImportResult])
async def import_multiple_parts(
    part_names: list[str],
    db: Session = Depends(get_db),
):
    """
    Import multiple parts from iGEM Registry.

    Accepts a list of part names and imports them all.
    """
    results = []

    for part_name in part_names[:20]:  # Limit to 20 at a time
        # Check if already exists
        existing = db.query(Part).filter(Part.name == part_name).first()
        if existing:
            results.append(ImportResult(
                success=False,
                message=f"Part {part_name} already exists",
                part=None
            ))
            continue

        # Fetch from iGEM
        igem_part = await fetch_igem_part(part_name)
        if not igem_part:
            results.append(ImportResult(
                success=False,
                message=f"Part {part_name} not found in iGEM",
                part=None
            ))
            continue

        # Create local part
        db_part = Part(
            name=igem_part["name"],
            type=igem_part["type"],
            description=igem_part.get("description"),
            sequence=igem_part["sequence"],
            organism=igem_part.get("organism"),
            source="iGEM",
        )
        db.add(db_part)

        results.append(ImportResult(
            success=True,
            message=f"Imported {part_name}",
            part=igem_part
        ))

    db.commit()
    return results
