"""API endpoints for sequencing file import and alignment."""

import json

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from app.services.sequencing import parse_sequencing_file, align_to_pathway

router = APIRouter(prefix="/api/v1/import", tags=["sequencing"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class PartResult(BaseModel):
    name: str
    type: str
    length: int
    similarity: float


class ParseResult(BaseModel):
    sequence: str
    avg_quality: float
    format: str
    read_name: str
    num_reads: int
    sequence_length: int


class AlignmentResult(BaseModel):
    overall_similarity: float
    coverage_percent: float
    matching_bases: int
    reference_length: int
    query_length: int
    part_results: list[PartResult]


class SequencingImportResponse(BaseModel):
    parse_result: ParseResult
    alignment: Optional[AlignmentResult] = None


@router.post("/sequencing", response_model=SequencingImportResponse)
async def import_sequencing(
    file: UploadFile = File(..., description="FASTQ or AB1 sequencing file"),
    pathway_parts_json: Optional[str] = Form(
        default=None,
        description="JSON array of pathway parts for alignment",
    ),
):
    """
    Import a sequencing file (FASTQ or AB1) and optionally align against pathway parts.

    Upload a sequencing file to parse sequence and quality data.
    Optionally provide pathway_parts_json to align the read against your design.
    """
    # Validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Parse the sequencing file
    try:
        parse_result = parse_sequencing_file(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to parse sequencing file: {str(e)}"
        )

    # Strip quality_scores from response (can be very large)
    response_parse = {
        k: v for k, v in parse_result.items() if k != "quality_scores"
    }

    # Optionally align to pathway parts
    alignment = None
    if pathway_parts_json:
        try:
            parts = json.loads(pathway_parts_json)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="Invalid JSON in pathway_parts_json"
            )

        try:
            alignment = align_to_pathway(parse_result["sequence"], parts)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return SequencingImportResponse(
        parse_result=ParseResult(**response_parse),
        alignment=AlignmentResult(**alignment) if alignment else None,
    )
