"""API routes for structure prediction via Protenix and ESM services."""

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
ESM_SERVICE_URL = os.environ.get("ESM_SERVICE_URL", "http://localhost:8002")

# Track which service owns each job (job_id -> service_url)
_job_service_map: dict[str, str] = {}


def _get_service_url(model_name: str) -> str:
    """Determine which GPU service to use based on model name prefix."""
    if model_name.startswith("protenix_"):
        return PROTENIX_SERVICE_URL
    if model_name.startswith("esm"):
        return ESM_SERVICE_URL
    # Default to Protenix
    return PROTENIX_SERVICE_URL


@router.post("/predict", response_model=StructurePredictResponse)
async def predict_structure(request: StructurePredictRequest):
    """Submit a structure prediction request.

    Routes to Protenix or ESM service based on the selected model.
    """
    service_url = _get_service_url(request.model_name)

    protenix_payload = {
        "name": request.name,
        "sequences": [chain.model_dump(exclude_none=True) for chain in request.chains],
        "model_name": request.model_name,
        "num_seeds": 1,
        "num_samples": request.num_samples,
    }

    service_name = "ESM" if service_url == ESM_SERVICE_URL else "Protenix"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{service_url}/predict",
                json=protenix_payload,
            )
            response.raise_for_status()
            data = response.json()
            # Track which service owns this job
            _job_service_map[data["job_id"]] = service_url
            return StructurePredictResponse(
                job_id=data["job_id"],
                status=data["status"],
                message=f"Prediction job submitted to {service_name}: {data['status']}",
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"{service_name} service is not available. Ensure the GPU service is running.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", f"{service_name} service error"),
            )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status of a prediction job."""
    service_url = _job_service_map.get(job_id)

    if service_url:
        # We know which service owns this job
        return await _poll_service(service_url, job_id)

    # Try both services (for jobs created before tracking started)
    for url in [PROTENIX_SERVICE_URL, ESM_SERVICE_URL]:
        try:
            result = await _poll_service(url, job_id)
            _job_service_map[job_id] = url
            return result
        except HTTPException as e:
            if e.status_code != 404:
                raise
            continue

    raise HTTPException(status_code=404, detail="Job not found")


async def _poll_service(service_url: str, job_id: str) -> dict:
    """Poll a specific service for job status."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{service_url}/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="GPU service is not available.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Job not found"),
            )


@router.get("/jobs/{job_id}/structure")
async def download_structure(job_id: str):
    """Download the predicted structure file."""
    service_url = _job_service_map.get(job_id)

    if not service_url:
        # Try both services
        for url in [PROTENIX_SERVICE_URL, ESM_SERVICE_URL]:
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    response = await client.get(f"{url}/jobs/{job_id}/structure")
                    if response.status_code == 200:
                        service_url = url
                        _job_service_map[job_id] = url
                        return StreamingResponse(
                            iter([response.content]),
                            media_type=response.headers.get(
                                "content-type", "chemical/x-mmcif"
                            ),
                            headers={
                                "Content-Disposition": f'attachment; filename="{job_id}.cif"'
                            },
                        )
                except httpx.ConnectError:
                    continue
        raise HTTPException(status_code=404, detail="Structure not found")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(f"{service_url}/jobs/{job_id}/structure")
            response.raise_for_status()
            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("content-type", "chemical/x-mmcif"),
                headers={
                    "Content-Disposition": f'attachment; filename="{job_id}.cif"'
                },
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="GPU service is not available.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Structure not available"),
            )


@router.get("/models")
async def list_models():
    """List available models from all GPU services (Protenix + ESM)."""
    all_models = []

    for service_url, service_name in [
        (PROTENIX_SERVICE_URL, "Protenix"),
        (ESM_SERVICE_URL, "ESM"),
    ]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{service_url}/models")
                response.raise_for_status()
                data = response.json()
                all_models.extend(data.get("models", []))
            except Exception:
                # Service unavailable, skip its models
                pass

    # Fallback if no services are reachable
    if not all_models:
        all_models = [
            {
                "name": "protenix_base_default_v1.0.0",
                "description": "Protenix base model (default)",
                "parameters_m": 368.48,
                "features": ["MSA", "Template", "RNA MSA"],
                "speed_tier": "slow",
                "default": True,
                "loaded": False,
            }
        ]

    return {"models": all_models}


@router.post("/preload")
async def preload_model(request: dict):
    """Preload a model into GPU memory on the appropriate service."""
    model_name = request.get("model_name", "")
    service_url = _get_service_url(model_name)
    service_name = "ESM" if service_url == ESM_SERVICE_URL else "Protenix"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{service_url}/preload",
                json={"model_name": model_name},
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"{service_name} service is not available.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Preload failed"),
            )
