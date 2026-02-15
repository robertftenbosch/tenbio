"""API endpoints for pathway export (SBOL3)."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Literal

from app.services.sbol3_export import export_pathway_sbol3

router = APIRouter(prefix="/api/v1/export", tags=["export"])


class PartExport(BaseModel):
    name: str
    type: str
    sequence: str
    description: str = ""


class Sbol3ExportRequest(BaseModel):
    name: str = Field(..., description="Pathway name")
    description: str = Field(default="", description="Pathway description")
    parts: list[PartExport] = Field(..., description="Ordered list of parts")
    format: Literal["json-ld", "rdf-xml"] = Field(
        default="json-ld", description="SBOL3 output format"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "my_pathway",
                "description": "GFP expression cassette",
                "parts": [
                    {
                        "name": "pTac",
                        "type": "promoter",
                        "sequence": "AATTGTGAGCGGATAACAATT",
                        "description": "Tac promoter",
                    },
                    {
                        "name": "GFP",
                        "type": "gene",
                        "sequence": "ATGGTGAGCAAGGGCGAGGAG",
                        "description": "Green fluorescent protein",
                    },
                ],
                "format": "json-ld",
            }
        }


@router.post("/sbol3")
def export_sbol3(request: Sbol3ExportRequest):
    """
    Export a pathway design as SBOL3.

    Returns the SBOL3 document as a file download (JSON-LD or RDF/XML).
    """
    try:
        parts_dicts = [p.model_dump() for p in request.parts]
        content = export_pathway_sbol3(
            name=request.name,
            description=request.description,
            parts=parts_dicts,
            file_format=request.format,
        )

        if request.format == "rdf-xml":
            media_type = "application/rdf+xml"
            extension = "xml"
        else:
            media_type = "application/ld+json"
            extension = "jsonld"

        filename = f"{request.name or 'pathway'}.{extension}"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
