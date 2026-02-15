"""Background worker for processing ESMFold structure prediction jobs."""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Optional

from app.schemas import ConfidenceScores, JobStatus, PredictionRequest

logger = logging.getLogger(__name__)

# In-memory job store
_jobs: dict[str, JobStatus] = {}
_job_output_dirs: dict[str, str] = {}
_job_queue: Queue[str] = Queue()
_job_requests: dict[str, PredictionRequest] = {}

# Model registry -- only one model loaded at a time (GPU VRAM constraint)
_model = None
_tokenizer = None
_loaded_model_name: Optional[str] = None
_model_lock = threading.Lock()
_preloading: bool = False

BASE_OUTPUT_DIR = os.environ.get("ESM_OUTPUT_DIR", "/app/output")

# Catalog of available ESM model variants.
MODEL_CATALOG: dict[str, dict] = {
    "esmfold_v1": {
        "description": "ESMFold v1 -- fast single-chain structure prediction",
        "parameters_m": 690.0,
        "features": ["Protein"],
        "speed_tier": "fast",
        "default": True,
    },
}


def get_model(model_name: str):
    """Load the requested ESM model, swapping if necessary."""
    global _model, _tokenizer, _loaded_model_name

    if model_name not in MODEL_CATALOG:
        raise ValueError(f"Unknown model: {model_name}")

    if _model is not None and _loaded_model_name == model_name:
        return _model

    with _model_lock:
        if _model is not None and _loaded_model_name == model_name:
            return _model

        # Unload current model
        if _model is not None:
            logger.info(f"Unloading model '{_loaded_model_name}' to load '{model_name}'...")
            del _model
            _model = None
            _tokenizer = None
            _loaded_model_name = None
            import torch

            torch.cuda.empty_cache()

        catalog_entry = MODEL_CATALOG[model_name]
        logger.info(
            f"Loading model '{model_name}' ({catalog_entry['parameters_m']}M params)..."
        )

        if model_name == "esmfold_v1":
            import torch
            import esm

            _model = esm.pretrained.esmfold_v1()
            _model = _model.eval()
            if torch.cuda.is_available():
                _model = _model.cuda()
            # Optimize memory for long sequences
            _model.set_chunk_size(128)

        _loaded_model_name = model_name
        logger.info(f"Model '{model_name}' loaded successfully.")
        return _model


def preload_model(model_name: str) -> None:
    """Eagerly load a model into GPU memory."""
    global _preloading
    _preloading = True
    try:
        get_model(model_name)
    finally:
        _preloading = False


def is_model_loaded() -> bool:
    """Check if any model has been loaded."""
    return _model is not None


def get_loaded_model() -> Optional[str]:
    """Return the name of the currently loaded model, or None."""
    return _loaded_model_name


def is_preloading() -> bool:
    """Check if a model is currently being preloaded."""
    return _preloading


def list_models() -> list[dict]:
    """Return all models from the catalog with their loaded status."""
    result = []
    for name, info in MODEL_CATALOG.items():
        result.append(
            {
                "name": name,
                "description": info["description"],
                "parameters_m": info["parameters_m"],
                "features": info["features"],
                "speed_tier": info["speed_tier"],
                "default": info["default"],
                "loaded": _loaded_model_name == name,
            }
        )
    return result


def _run_esmfold(sequence: str, output_dir: str) -> tuple[Optional[str], Optional[ConfidenceScores]]:
    """Run ESMFold inference on a single protein sequence.

    Returns (cif_path, confidence_scores).
    """
    import torch
    import numpy as np

    model = get_model("esmfold_v1")

    with torch.no_grad():
        output = model.infer_pdb(sequence)

    # Save PDB output
    pdb_path = os.path.join(output_dir, "prediction.pdb")
    with open(pdb_path, "w") as f:
        f.write(output)

    # Convert PDB to CIF for consistency with Protenix API contract
    cif_path = os.path.join(output_dir, "rank_001.cif")
    try:
        from Bio.PDB import PDBParser, MMCIFIO
        import io as sio

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("pred", pdb_path)
        cif_io = MMCIFIO()
        cif_io.set_structure(structure)
        cif_io.save(cif_path)
    except Exception as e:
        logger.warning(f"PDB to CIF conversion failed, serving PDB: {e}")
        cif_path = pdb_path

    # Extract confidence scores from ESMFold output
    # ESMFold includes pTM and mean pLDDT in the model output
    confidence = None
    try:
        output_tensors = model.infer(sequence, num_recycles=4)
        ptm = float(output_tensors["ptm"].cpu())
        plddt = float(output_tensors["plddt"].cpu().mean()) * 100  # Scale to 0-100
        confidence = ConfidenceScores(
            plddt=round(plddt, 2),
            ptm=round(ptm, 4),
        )
        # Save confidence to JSON
        conf_path = os.path.join(output_dir, "confidence_summary.json")
        with open(conf_path, "w") as f:
            json.dump(
                {"plddt": confidence.plddt, "ptm": confidence.ptm},
                f,
                indent=2,
            )
    except Exception as e:
        logger.warning(f"Failed to extract confidence scores: {e}")

    return cif_path, confidence


def submit_job(request: PredictionRequest) -> str:
    """Submit a prediction job to the queue. Returns the job ID."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    _jobs[job_id] = JobStatus(
        job_id=job_id,
        status="queued",
        progress="Waiting in queue",
        created_at=now,
    )
    _job_requests[job_id] = request
    _job_queue.put(job_id)

    logger.info(f"Job {job_id} submitted: {request.name}")
    return job_id


def get_job_status(job_id: str) -> Optional[JobStatus]:
    """Get the status of a job by ID."""
    return _jobs.get(job_id)


def get_job_output_dir(job_id: str) -> Optional[str]:
    """Get the output directory for a completed job."""
    return _job_output_dirs.get(job_id)


def _worker_loop():
    """Background worker thread that processes prediction jobs sequentially."""
    while True:
        job_id = _job_queue.get()
        if job_id is None:
            break

        request = _job_requests.get(job_id)
        if not request:
            continue

        now = datetime.now(timezone.utc)
        _jobs[job_id] = JobStatus(
            job_id=job_id,
            status="running",
            progress="Initializing model",
            created_at=_jobs[job_id].created_at,
            started_at=now,
        )

        try:
            # Validate: ESMFold only supports single protein chains
            protein_chains = [c for c in request.sequences if c.type == "protein"]
            non_protein = [c for c in request.sequences if c.type != "protein"]

            if not protein_chains:
                raise ValueError("ESMFold requires at least one protein chain.")
            if non_protein:
                logger.warning(
                    f"ESMFold only supports protein chains. "
                    f"Ignoring {len(non_protein)} non-protein chain(s)."
                )

            # Use the first protein chain (ESMFold predicts single chains)
            sequence = protein_chains[0].sequence
            if not sequence:
                raise ValueError("Protein sequence is empty.")

            # Create output directory
            job_output_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            _jobs[job_id].progress = "Loading model and running inference"

            cif_path, confidence = _run_esmfold(sequence, job_output_dir)

            _job_output_dirs[job_id] = job_output_dir

            now = datetime.now(timezone.utc)
            _jobs[job_id] = JobStatus(
                job_id=job_id,
                status="completed",
                progress="Done",
                created_at=_jobs[job_id].created_at,
                started_at=_jobs[job_id].started_at,
                completed_at=now,
                confidence=confidence,
                structure_available=cif_path is not None,
            )
            logger.info(f"Job {job_id} completed successfully.")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            now = datetime.now(timezone.utc)
            _jobs[job_id] = JobStatus(
                job_id=job_id,
                status="failed",
                progress="Failed",
                created_at=_jobs[job_id].created_at,
                started_at=_jobs[job_id].started_at,
                completed_at=now,
                error=str(e),
            )

        finally:
            _job_queue.task_done()


# Start the background worker thread
_worker_thread = threading.Thread(target=_worker_loop, daemon=True)
_worker_thread.start()
