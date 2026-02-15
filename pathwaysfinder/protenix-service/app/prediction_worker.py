"""Background worker for processing Protenix prediction jobs."""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from typing import Optional

from app.schemas import ChainInput, ConfidenceScores, JobStatus, PredictionRequest

logger = logging.getLogger(__name__)

# In-memory job store
_jobs: dict[str, JobStatus] = {}
_job_output_dirs: dict[str, str] = {}
_job_queue: Queue[str] = Queue()
_job_requests: dict[str, PredictionRequest] = {}

# Model registry -- only one runner loaded at a time (GPU VRAM constraint)
_runner = None
_loaded_model_name: Optional[str] = None
_runner_lock = threading.Lock()
_preloading: bool = False

BASE_OUTPUT_DIR = os.environ.get("PROTENIX_OUTPUT_DIR", "/app/output")

# Catalog of all available Protenix model variants with metadata.
# Keys match model names from configs/configs_model_type.py.
MODEL_CATALOG: dict[str, dict] = {
    "protenix_base_default_v1.0.0": {
        "description": "Base model v1.0 (MSA + Template + RNA MSA)",
        "parameters_m": 368.48,
        "features": ["MSA", "Template", "RNA MSA"],
        "speed_tier": "slow",
        "default": True,
        "n_step": 200,
        "n_cycle": 10,
    },
    "protenix_base_20250630_v1.0.0": {
        "description": "Base model v1.0 (newer PDB data, 2025-06-30 cutoff)",
        "parameters_m": 368.48,
        "features": ["MSA", "Template", "RNA MSA"],
        "speed_tier": "slow",
        "default": False,
        "n_step": 200,
        "n_cycle": 10,
    },
    "protenix_base_default_v0.5.0": {
        "description": "Base model v0.5 (MSA only)",
        "parameters_m": 368.09,
        "features": ["MSA"],
        "speed_tier": "slow",
        "default": False,
        "n_step": 200,
        "n_cycle": 10,
    },
    "protenix_base_constraint_v0.5.0": {
        "description": "Base model v0.5 with constraints (pocket/contact)",
        "parameters_m": 368.30,
        "features": ["MSA", "Constraints"],
        "speed_tier": "slow",
        "default": False,
        "n_step": 200,
        "n_cycle": 10,
    },
    "protenix_mini_esm_v0.5.0": {
        "description": "Mini model with ESM embeddings (no MSA search needed)",
        "parameters_m": 135.22,
        "features": ["ESM", "MSA"],
        "speed_tier": "fast",
        "default": False,
        "n_step": 5,
        "n_cycle": 4,
    },
    "protenix_mini_ism_v0.5.0": {
        "description": "Mini model with ISM embeddings",
        "parameters_m": 135.22,
        "features": ["ISM", "MSA"],
        "speed_tier": "fast",
        "default": False,
        "n_step": 5,
        "n_cycle": 4,
    },
    "protenix_mini_default_v0.5.0": {
        "description": "Mini model v0.5 (MSA only)",
        "parameters_m": 134.06,
        "features": ["MSA"],
        "speed_tier": "fast",
        "default": False,
        "n_step": 5,
        "n_cycle": 4,
    },
    "protenix_tiny_default_v0.5.0": {
        "description": "Tiny model v0.5 (MSA only, fastest)",
        "parameters_m": 109.50,
        "features": ["MSA"],
        "speed_tier": "fast",
        "default": False,
        "n_step": 5,
        "n_cycle": 4,
    },
}


def get_runner(model_name: str):
    """Get the InferenceRunner for the given model, swapping if necessary.

    Only one model can be loaded at a time due to GPU VRAM constraints.
    If a different model is requested, the current one is unloaded first.
    """
    global _runner, _loaded_model_name

    if model_name not in MODEL_CATALOG:
        raise ValueError(f"Unknown model: {model_name}")

    # Already loaded
    if _runner is not None and _loaded_model_name == model_name:
        return _runner

    with _runner_lock:
        # Double-check after acquiring lock
        if _runner is not None and _loaded_model_name == model_name:
            return _runner

        # Unload current model if one is loaded
        if _runner is not None:
            logger.info(f"Unloading model '{_loaded_model_name}' to load '{model_name}'...")
            del _runner
            _runner = None
            _loaded_model_name = None
            import torch

            torch.cuda.empty_cache()

        # Load the requested model
        catalog_entry = MODEL_CATALOG[model_name]
        logger.info(f"Loading model '{model_name}' ({catalog_entry['parameters_m']}M params)...")
        from runner.batch_inference import get_default_runner

        _runner = get_default_runner(
            seeds=[101],
            n_sample=5,
            n_step=catalog_entry["n_step"],
            n_cycle=catalog_entry["n_cycle"],
            model_name=model_name,
        )
        _loaded_model_name = model_name
        logger.info(f"Model '{model_name}' loaded successfully.")
        return _runner


def preload_model(model_name: str) -> None:
    """Eagerly load a model into GPU memory (called from preload endpoint or startup)."""
    global _preloading
    _preloading = True
    try:
        get_runner(model_name)
    finally:
        _preloading = False


def is_model_loaded() -> bool:
    """Check if any model has been loaded."""
    return _runner is not None


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


def build_protenix_input(request: PredictionRequest) -> list[dict]:
    """Convert a tenbio prediction request to Protenix input JSON format.

    Protenix expects a list of sample dictionaries, each with:
    - name: job name
    - sequences: list of entity dicts (proteinChain, dnaSequence, rnaSequence, ligand, ion)
    - covalent_bonds: optional bonds (empty for now)
    """
    sample: dict = {
        "name": request.name,
        "sequences": [],
        "covalent_bonds": [],
    }

    for chain in request.sequences:
        if chain.type == "protein":
            sample["sequences"].append(
                {
                    "proteinChain": {
                        "sequence": chain.sequence,
                        "count": chain.count,
                    }
                }
            )
        elif chain.type == "dna":
            sample["sequences"].append(
                {
                    "dnaSequence": {
                        "sequence": chain.sequence,
                        "count": chain.count,
                    }
                }
            )
        elif chain.type == "rna":
            sample["sequences"].append(
                {
                    "rnaSequence": {
                        "sequence": chain.sequence,
                        "count": chain.count,
                    }
                }
            )
        elif chain.type == "ligand":
            ligand_entry: dict = {"count": chain.count}
            # CCD code or SMILES
            if chain.ligand_id:
                ligand_entry["ligand"] = chain.ligand_id
            ligand_entry.setdefault("ligand", "UNK")
            sample["sequences"].append({"ligand": ligand_entry})
        elif chain.type == "ion":
            sample["sequences"].append(
                {
                    "ion": {
                        "ion": chain.ion_id or "MG",
                        "count": chain.count,
                    }
                }
            )

    return [sample]


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


def _find_output_cif(output_dir: str) -> Optional[str]:
    """Find the best-ranked CIF file in the output directory."""
    output_path = Path(output_dir)
    # Protenix outputs CIF files in subdirectories
    cif_files = list(output_path.rglob("*.cif"))
    if not cif_files:
        return None
    # Prefer ranked files (e.g., rank_001.cif)
    ranked = [f for f in cif_files if "rank" in f.name]
    if ranked:
        ranked.sort()
        return str(ranked[0])
    return str(cif_files[0])


def _parse_confidence(output_dir: str) -> Optional[ConfidenceScores]:
    """Parse confidence scores from Protenix output."""
    output_path = Path(output_dir)
    # Look for summary JSON files
    json_files = list(output_path.rglob("*summary*.json")) + list(
        output_path.rglob("*confidence*.json")
    )
    if not json_files:
        return None

    try:
        with open(json_files[0], "r") as f:
            data = json.load(f)
        return ConfidenceScores(
            plddt=data.get("plddt"),
            ptm=data.get("ptm"),
            iptm=data.get("iptm"),
            ranking_score=data.get("ranking_score"),
        )
    except Exception as e:
        logger.warning(f"Failed to parse confidence scores: {e}")
        return None


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
            # Build Protenix input JSON
            protenix_input = build_protenix_input(request)

            # Create output directory for this job
            job_output_dir = os.path.join(BASE_OUTPUT_DIR, job_id)
            os.makedirs(job_output_dir, exist_ok=True)

            # Write input JSON to temp file
            input_json_path = os.path.join(job_output_dir, "input.json")
            with open(input_json_path, "w") as f:
                json.dump(protenix_input, f, indent=2)

            _jobs[job_id].progress = "Loading model and running inference"

            # Get the runner for the requested model (swaps if needed)
            runner = get_runner(request.model_name)

            # Update runner configs for this job
            runner.configs["input_json_path"] = input_json_path
            runner.configs["dump_dir"] = job_output_dir
            runner.configs["seeds"] = list(range(101, 101 + request.num_seeds))
            runner.configs["sample_diffusion"]["N_sample"] = request.num_samples

            from runner.inference import infer_predict

            infer_predict(runner, runner.configs)

            # Parse results
            _job_output_dirs[job_id] = job_output_dir
            confidence = _parse_confidence(job_output_dir)
            cif_path = _find_output_cif(job_output_dir)

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
