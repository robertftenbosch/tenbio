"""API routes for structure prediction via Protenix and ESM services."""

import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prediction_job import PredictionJob
from app.schemas.structure import (
    JobStatusResponse,
    StructurePredictRequest,
    StructurePredictResponse,
)

router = APIRouter(prefix="/api/v1/structure", tags=["structure prediction"])

PROTENIX_SERVICE_URL = os.environ.get("PROTENIX_SERVICE_URL", "http://localhost:8001")
ESM_SERVICE_URL = os.environ.get("ESM_SERVICE_URL", "http://localhost:8002")

_SERVICE_URLS = {
    "protenix": PROTENIX_SERVICE_URL,
    "esm": ESM_SERVICE_URL,
}


def _resolve_service(model_name: str) -> str:
    """Pick the worker name for a model. Default to protenix."""
    if model_name.startswith("esm"):
        return "esm"
    return "protenix"


def _service_url(service: str) -> str:
    return _SERVICE_URLS.get(service, PROTENIX_SERVICE_URL)


@router.post("/predict", response_model=StructurePredictResponse)
async def predict_structure(
    request: StructurePredictRequest,
    db: Session = Depends(get_db),
):
    """Submit a structure prediction request.

    Routes to Protenix or ESM based on the model name and persists a
    PredictionJob row so we still know which worker owns the job after an
    API restart.
    """
    service = _resolve_service(request.model_name)
    url = _service_url(service)

    payload = {
        "name": request.name,
        "sequences": [chain.model_dump(exclude_none=True) for chain in request.chains],
        "model_name": request.model_name,
        "num_seeds": 1,
        "num_samples": request.num_samples,
    }
    service_label = "ESM" if service == "esm" else "Protenix"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(f"{url}/predict", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"{service_label} service is not available. Ensure the GPU service is running.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", f"{service_label} service error"),
            )

    job_id = data["job_id"]
    db.add(
        PredictionJob(
            id=job_id,
            service=service,
            model_name=request.model_name,
            request_json=payload,
            last_status=data.get("status"),
            last_status_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    return StructurePredictResponse(
        job_id=job_id,
        status=data["status"],
        message=f"Prediction job submitted to {service_label}: {data['status']}",
    )


@router.get("/jobs", response_model=list[dict])
def list_jobs(limit: int = 50, db: Session = Depends(get_db)):
    """List recent prediction jobs known to this API instance.

    Returns the cached `last_status`; for live status, poll `/jobs/{id}`.
    """
    rows = (
        db.query(PredictionJob)
        .order_by(PredictionJob.created_at.desc())
        .limit(min(max(limit, 1), 200))
        .all()
    )
    return [
        {
            "job_id": r.id,
            "service": r.service,
            "model_name": r.model_name,
            "name": (r.request_json or {}).get("name") if r.request_json else None,
            "last_status": r.last_status,
            "last_status_at": r.last_status_at.isoformat() if r.last_status_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def _poll_url(url: str, job_id: str) -> dict:
    """Poll a specific worker URL for job status."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{url}/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="GPU service is not available.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Job not found"),
            )


def _adopt_legacy_job(
    db: Session, job_id: str, service: str, status: Optional[str]
) -> None:
    """Persist a job we discovered by probing — covers jobs created before this PR."""
    if db.get(PredictionJob, job_id):
        return
    db.add(
        PredictionJob(
            id=job_id,
            service=service,
            model_name="unknown",
            request_json={},
            last_status=status,
            last_status_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Poll the status of a prediction job."""
    record = db.get(PredictionJob, job_id)

    if record is not None:
        result = await _poll_url(_service_url(record.service), job_id)
        record.last_status = result.get("status")
        record.last_status_at = datetime.now(timezone.utc)
        db.commit()
        return result

    # Legacy fallback: probe both workers for jobs created before persistence.
    for service, url in _SERVICE_URLS.items():
        try:
            result = await _poll_url(url, job_id)
        except HTTPException as e:
            if e.status_code == 404:
                continue
            raise
        _adopt_legacy_job(db, job_id, service, result.get("status"))
        return result

    raise HTTPException(status_code=404, detail="Job not found")


@router.get("/jobs/{job_id}/structure")
async def download_structure(job_id: str, db: Session = Depends(get_db)):
    """Download the predicted structure file."""
    record = db.get(PredictionJob, job_id)
    candidate_urls: list[tuple[str, str]] = []
    if record is not None:
        candidate_urls.append((record.service, _service_url(record.service)))
    else:
        candidate_urls = list(_SERVICE_URLS.items())

    last_error: Optional[HTTPException] = None
    for service, url in candidate_urls:
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(f"{url}/jobs/{job_id}/structure")
            except httpx.ConnectError:
                last_error = HTTPException(
                    status_code=503, detail="GPU service is not available."
                )
                continue
            if response.status_code == 404:
                last_error = HTTPException(status_code=404, detail="Structure not found")
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = "Structure not available"
                try:
                    detail = e.response.json().get("detail", detail)
                except Exception:
                    pass
                last_error = HTTPException(status_code=e.response.status_code, detail=detail)
                continue

            if record is None:
                _adopt_legacy_job(db, job_id, service, "completed")

            return StreamingResponse(
                iter([response.content]),
                media_type=response.headers.get("content-type", "chemical/x-mmcif"),
                headers={"Content-Disposition": f'attachment; filename="{job_id}.cif"'},
            )

    raise last_error or HTTPException(status_code=404, detail="Structure not found")


@router.get("/models")
async def list_models():
    """List available models from all GPU services (Protenix + ESM)."""
    all_models = []

    for url, service_name in [
        (PROTENIX_SERVICE_URL, "Protenix"),
        (ESM_SERVICE_URL, "ESM"),
    ]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{url}/models")
                response.raise_for_status()
                data = response.json()
                all_models.extend(data.get("models", []))
            except Exception:
                # Service unavailable, skip its models
                pass

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
    service = _resolve_service(model_name)
    url = _service_url(service)
    service_label = "ESM" if service == "esm" else "Protenix"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{url}/preload",
                json={"model_name": model_name},
            )
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"{service_label} service is not available.",
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json().get("detail", "Preload failed"),
            )
