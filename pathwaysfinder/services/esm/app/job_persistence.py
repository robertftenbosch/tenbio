"""On-disk persistence for GPU prediction jobs.

The worker keeps `_jobs`, `_job_output_dirs`, and `_job_requests` in memory.
Without persistence, every container restart wipes those — finished jobs
appear lost (the CIF file is still on the volume, but the API can no longer
locate it), and queued jobs are never run.

This module mirrors each job's state into a JSON file at
`{BASE_OUTPUT_DIR}/_jobs/{job_id}.json`. The file is rewritten on every
state transition (atomic via tmp-file + rename). On worker startup,
`restore_jobs` scans the directory and rebuilds the in-memory state:

- `queued` jobs are re-enqueued so they actually run.
- `running` jobs (the worker died mid-run) are marked `failed` with reason
  "worker restarted" and persisted as such — the user can resubmit.
- `completed` / `failed` jobs are restored as-is so status polling works.

The persistence dir lives inside the existing volume-mounted output
directory, so it survives container rebuilds without any docker-compose
changes.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from queue import Queue
from typing import Optional

from app.schemas import JobStatus, PredictionRequest

logger = logging.getLogger(__name__)

_PERSIST_SUBDIR = "_jobs"


def _persist_dir(base_output_dir: str) -> str:
    return os.path.join(base_output_dir, _PERSIST_SUBDIR)


def _path_for(base_output_dir: str, job_id: str) -> str:
    return os.path.join(_persist_dir(base_output_dir), f"{job_id}.json")


def persist_job(
    base_output_dir: str,
    job_id: str,
    status: JobStatus,
    request: Optional[PredictionRequest],
    output_dir: Optional[str],
) -> None:
    """Atomically write a job's full state to disk.

    Failures are logged but never raised — losing one persistence write must
    not crash an in-progress prediction.
    """
    try:
        os.makedirs(_persist_dir(base_output_dir), exist_ok=True)
        payload = {
            "status": json.loads(status.model_dump_json()),
            "request": (
                json.loads(request.model_dump_json()) if request is not None else None
            ),
            "output_dir": output_dir,
        }
        target = _path_for(base_output_dir, job_id)
        # Atomic: write to tmp in same dir, then rename.
        fd, tmp = tempfile.mkstemp(
            prefix=f".{job_id}.", suffix=".tmp", dir=_persist_dir(base_output_dir)
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.warning(f"Failed to persist job {job_id}: {e}")


def delete_persisted_job(base_output_dir: str, job_id: str) -> None:
    """Remove a job's persisted state. Best-effort."""
    try:
        os.unlink(_path_for(base_output_dir, job_id))
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"Failed to delete persisted job {job_id}: {e}")


def restore_jobs(
    base_output_dir: str,
    jobs: dict[str, JobStatus],
    requests: dict[str, PredictionRequest],
    output_dirs: dict[str, str],
    queue: Queue,
) -> dict[str, int]:
    """Restore persisted jobs into the in-memory dicts.

    Returns a counter dict like {"restored": 5, "requeued": 2, "failed_running": 1}
    so the caller can log a useful summary.
    """
    counts = {"restored": 0, "requeued": 0, "failed_running": 0}
    pdir = _persist_dir(base_output_dir)
    if not os.path.isdir(pdir):
        return counts

    for entry in sorted(os.listdir(pdir)):
        if not entry.endswith(".json"):
            continue
        path = os.path.join(pdir, entry)
        try:
            with open(path, "r") as f:
                payload = json.load(f)
            status = JobStatus.model_validate(payload["status"])
            request = (
                PredictionRequest.model_validate(payload["request"])
                if payload.get("request") is not None
                else None
            )
            output_dir = payload.get("output_dir")
        except Exception as e:
            logger.warning(f"Skipping malformed persisted job {entry}: {e}")
            continue

        job_id = status.job_id

        # A `running` job means the worker died mid-prediction. Mark failed
        # and persist that decision so it stays consistent across a second
        # restart loop.
        if status.status == "running":
            now = datetime.now(timezone.utc)
            status = JobStatus(
                job_id=job_id,
                status="failed",
                progress="Failed",
                created_at=status.created_at,
                started_at=status.started_at,
                completed_at=now,
                error="Worker restarted before this job finished. Please resubmit.",
            )
            counts["failed_running"] += 1
            persist_job(base_output_dir, job_id, status, request, output_dir)

        jobs[job_id] = status
        if output_dir:
            output_dirs[job_id] = output_dir
        if request is not None:
            requests[job_id] = request

        if status.status == "queued" and request is not None:
            queue.put(job_id)
            counts["requeued"] += 1

        counts["restored"] += 1

    return counts
