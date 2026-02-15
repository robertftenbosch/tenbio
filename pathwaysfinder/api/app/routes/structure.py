"""API routes for structure prediction via Protenix service."""

import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.structure import (
    JobStatusResponse,
    StructurePredictRequest,
    StructurePredictResponse,
)

router = APIRouter(prefix="/api/v1/structure", tags=["structure prediction"])

PROTENIX_SERVICE_URL = os.environ.get("PROTENIX_SERVICE_URL", "http://localhost:8001")


@router.post("/predict", response_model=StructurePredictResponse)
async def predict_structure(request: StructurePredictRequest):
    """Submit a structure prediction request to the Protenix service.

    Returns a job ID for polling.
    """
    # Convert tenbio request format to Protenix service format
    protenix_payload = {
        "name": request.name,
        "sequences": [chain.model_dump(exclude_none=True) for chain in request.chains],
        "model_name": request.model_name,
        "num_seeds": 1,
        "num_samples": request.num_samples,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{PROTENIX_SERVICE_URL}/predict",
                json=protenix_payload,
            )
            response.raise_for_status()
            data = response.json()
            return StructurePredictResponse(
                job_id=data["job_id"],
                status=data["status"],
                message=f"Prediction job submitted: {data['status']}",
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Protenix service is not available. Ensure the GPU service is running.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Protenix service error"),
            )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status of a prediction job."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{PROTENIX_SERVICE_URL}/jobs/{job_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Protenix service is not available.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Job not found"),
            )


@router.get("/jobs/{job_id}/structure")
async def download_structure(job_id: str):
    """Download the predicted structure CIF file."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(
                f"{PROTENIX_SERVICE_URL}/jobs/{job_id}/structure"
            )
            response.raise_for_status()
            return StreamingResponse(
                iter([response.content]),
                media_type="chemical/x-mmcif",
                headers={
                    "Content-Disposition": f'attachment; filename="{job_id}.cif"'
                },
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Protenix service is not available.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Structure not available"),
            )


@router.get("/models")
async def list_models():
    """List available Protenix model variants."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{PROTENIX_SERVICE_URL}/models")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            # Return default list if service is unavailable
            return {
                "models": [
                    {
                        "name": "protenix_base_default_v1.0.0",
                        "description": "Protenix base model (default)",
                        "default": True,
                    }
                ]
            }
        except Exception:
            return {
                "models": [
                    {
                        "name": "protenix_base_default_v1.0.0",
                        "description": "Protenix base model (default)",
                        "default": True,
                    }
                ]
            }
