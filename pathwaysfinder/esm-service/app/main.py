"""ESM Structure Prediction Service -- FastAPI wrapper around ESMFold."""

import logging
import os
import threading
from pathlib import Path

import torch
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.prediction_worker import (
    MODEL_CATALOG,
    get_job_output_dir,
    get_job_status,
    get_loaded_model,
    is_model_loaded,
    is_preloading,
    list_models as worker_list_models,
    preload_model,
    submit_job,
)
from app.schemas import (
    HealthResponse,
    JobStatus,
    PreloadRequest,
    PreloadResponse,
    PredictionRequest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ESM Structure Prediction Service",
    description="GPU-accelerated protein structure prediction powered by ESMFold.",
    version="0.1.0",
)


@app.on_event("startup")
def startup_preload():
    """If PRELOAD_MODEL is set, start loading the model in a background thread."""
    preload_name = os.environ.get("PRELOAD_MODEL")
    if preload_name:
        if preload_name not in MODEL_CATALOG:
            logger.warning(
                f"PRELOAD_MODEL='{preload_name}' is not a known ESM model, skipping."
            )
            return
        logger.info(f"Startup: preloading ESM model '{preload_name}'...")
        thread = threading.Thread(target=preload_model, args=(preload_name,), daemon=True)
        thread.start()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    gpu_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else None

    return HealthResponse(
        status="healthy",
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        model_loaded=is_model_loaded(),
        loaded_model=get_loaded_model(),
    )


@app.post("/predict", response_model=JobStatus)
def submit_prediction(request: PredictionRequest):
    """Submit a structure prediction job.

    ESMFold only supports protein chains (no DNA/RNA/ligand/ion complexes).
    """
    if request.model_name not in MODEL_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{request.model_name}'. Use GET /models for available models.",
        )

    # Validate chains
    protein_chains = [c for c in request.sequences if c.type == "protein"]
    if not protein_chains:
        raise HTTPException(
            status_code=400,
            detail="ESMFold requires at least one protein chain.",
        )

    for chain in protein_chains:
        if not chain.sequence:
            raise HTTPException(
                status_code=400, detail="Protein sequence is required."
            )

    job_id = submit_job(request)
    return get_job_status(job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def poll_job_status(job_id: str):
    """Poll the status of a prediction job."""
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@app.get("/jobs/{job_id}/structure")
def download_structure(job_id: str):
    """Download the predicted structure file."""
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    if status.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {status.status})",
        )

    output_dir = get_job_output_dir(job_id)
    if not output_dir:
        raise HTTPException(status_code=404, detail="Output directory not found")

    output_path = Path(output_dir)

    # Try CIF first, then PDB
    cif_files = list(output_path.glob("*.cif"))
    if cif_files:
        return FileResponse(
            path=str(cif_files[0]),
            media_type="chemical/x-mmcif",
            filename=f"{job_id}.cif",
        )

    pdb_files = list(output_path.glob("*.pdb"))
    if pdb_files:
        return FileResponse(
            path=str(pdb_files[0]),
            media_type="chemical/x-pdb",
            filename=f"{job_id}.pdb",
        )

    raise HTTPException(status_code=404, detail="No structure file found")


@app.get("/models")
def list_models():
    """List available ESM model variants."""
    return {"models": worker_list_models()}


@app.post("/preload", response_model=PreloadResponse)
def preload_model_endpoint(request: PreloadRequest, background_tasks: BackgroundTasks):
    """Preload a model into GPU memory."""
    if request.model_name not in MODEL_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{request.model_name}'. Use GET /models for available models.",
        )

    if get_loaded_model() == request.model_name:
        return PreloadResponse(
            model_name=request.model_name,
            status="already_loaded",
            message=f"Model '{request.model_name}' is already loaded.",
        )

    if is_preloading():
        return PreloadResponse(
            model_name=request.model_name,
            status="loading",
            message="A model is already being loaded. Please wait and try again.",
        )

    background_tasks.add_task(preload_model, request.model_name)

    return PreloadResponse(
        model_name=request.model_name,
        status="loading",
        message=f"Started loading model '{request.model_name}'. Poll GET /models to check status.",
    )
