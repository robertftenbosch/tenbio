"""PredictionJob model — tracks GPU structure-prediction jobs across API restarts.

The API used to keep a `_job_service_map: dict[str, str]` in memory to remember
which worker (Protenix vs ESM) owned each job_id. That map died on every API
restart, after which status polling fell back to probing both workers — slow
and unreliable. This table replaces that map with a durable record.

We also cache `last_status` and `last_status_at` so the new `GET /jobs`
endpoint can list recent jobs without polling a worker.
"""

from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func

from app.database import Base


class PredictionJob(Base):
    __tablename__ = "prediction_jobs"

    # Primary key: the worker-assigned job UUID (we do not generate a separate id).
    id = Column(String(36), primary_key=True)

    # Which worker owns the job. Currently "protenix" | "esm".
    service = Column(String(20), nullable=False, index=True)

    # Model variant the job was submitted against (e.g. protenix_base_default_v1.0.0).
    model_name = Column(String(100), nullable=False)

    # Original /predict payload sent to the worker, kept for audit and re-run.
    request_json = Column(JSON, nullable=False)

    # Cache of the last status we observed when polling the worker.
    # None until the first poll; updated on every successful poll.
    last_status = Column(String(20), nullable=True, index=True)
    last_status_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
