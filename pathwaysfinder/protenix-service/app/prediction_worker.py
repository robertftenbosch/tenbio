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

# Runner singleton (initialized lazily)
_runner = None
_runner_lock = threading.Lock()

BASE_OUTPUT_DIR = os.environ.get("PROTENIX_OUTPUT_DIR", "/app/output")


def _get_runner():
    """Lazily initialize the Protenix InferenceRunner."""
    global _runner
    if _runner is not None:
        return _runner

    with _runner_lock:
        if _runner is not None:
            return _runner

        logger.info("Initializing Protenix InferenceRunner...")
        from runner.batch_inference import get_default_runner

        _runner = get_default_runner(
            seeds=[101],
            n_sample=5,
            n_step=200,
            n_cycle=10,
            model_name="protenix_base_default_v1.0.0",
        )
        logger.info("Protenix InferenceRunner initialized successfully.")
        return _runner


def is_model_loaded() -> bool:
    """Check if the model has been loaded."""
    return _runner is not None


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

            # Get the runner and run inference
            runner = _get_runner()

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
