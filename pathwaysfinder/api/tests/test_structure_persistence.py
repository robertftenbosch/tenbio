"""Tests for the persistent PredictionJob layer in /api/v1/structure.

These tests mock httpx so they don't need real Protenix/ESM workers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.prediction_job import PredictionJob


def _mock_response(status_code: int, json_payload: dict | None = None, content: bytes = b""):
    """Build a minimal httpx.Response stand-in."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_payload or {})
    resp.content = content
    resp.headers = {"content-type": "application/json"}
    if 200 <= status_code < 300:
        resp.raise_for_status = MagicMock()
    else:
        err = httpx.HTTPStatusError("err", request=MagicMock(), response=resp)
        resp.raise_for_status = MagicMock(side_effect=err)
    return resp


def _async_client_returning(method_responses: dict[str, list]):
    """Build an AsyncMock httpx.AsyncClient context manager."""
    inst = MagicMock()
    posts = iter(method_responses.get("post", []))
    gets = iter(method_responses.get("get", []))
    inst.post = AsyncMock(side_effect=lambda *a, **kw: next(posts))
    inst.get = AsyncMock(side_effect=lambda *a, **kw: next(gets))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=inst)
    cm.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=cm)


def test_predict_persists_job_with_service_mapping(client, db_session):
    """POST /predict should write a PredictionJob row tagged to the right worker."""
    fake_async_client = _async_client_returning(
        {"post": [_mock_response(200, {"job_id": "job-protenix-1", "status": "queued"})]}
    )
    with patch("app.routes.structure.httpx.AsyncClient", fake_async_client):
        r = client.post(
            "/api/v1/structure/predict",
            json={
                "name": "test-1",
                "chains": [{"type": "protein", "sequence": "MVSK"}],
                "model_name": "protenix_base_default_v1.0.0",
                "num_samples": 1,
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["job_id"] == "job-protenix-1"

    row = db_session.get(PredictionJob, "job-protenix-1")
    assert row is not None
    assert row.service == "protenix"
    assert row.model_name == "protenix_base_default_v1.0.0"
    assert row.last_status == "queued"
    assert row.request_json["name"] == "test-1"


def test_predict_routes_esm_models_to_esm_worker(client, db_session):
    fake_async_client = _async_client_returning(
        {"post": [_mock_response(200, {"job_id": "job-esm-1", "status": "queued"})]}
    )
    with patch("app.routes.structure.httpx.AsyncClient", fake_async_client):
        r = client.post(
            "/api/v1/structure/predict",
            json={
                "name": "test-esm",
                "chains": [{"type": "protein", "sequence": "MVSK"}],
                "model_name": "esmfold_v1",
                "num_samples": 1,
            },
        )
    assert r.status_code == 200
    row = db_session.get(PredictionJob, "job-esm-1")
    assert row is not None
    assert row.service == "esm"


def test_status_uses_persisted_service_no_probing(client, db_session):
    """A status poll for a known job should hit only the recorded worker."""
    db_session.add(
        PredictionJob(
            id="known-job",
            service="esm",
            model_name="esmfold_v1",
            request_json={"name": "x"},
        )
    )
    db_session.commit()

    fake_async_client = _async_client_returning(
        {"get": [_mock_response(200, {"job_id": "known-job", "status": "completed"})]}
    )
    with patch("app.routes.structure.httpx.AsyncClient", fake_async_client):
        r = client.get("/api/v1/structure/jobs/known-job")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    db_session.expire_all()
    row = db_session.get(PredictionJob, "known-job")
    assert row.last_status == "completed"
    assert row.last_status_at is not None


def test_status_legacy_fallback_adopts_unknown_job(client, db_session):
    """A job that pre-dates persistence is found by probing and then persisted."""
    err_404 = _mock_response(404, {"detail": "Job not found"})
    ok = _mock_response(200, {"job_id": "legacy-1", "status": "running"})
    # Probes Protenix first (404), then ESM (200).
    fake_async_client = _async_client_returning({"get": [err_404, ok]})

    with patch("app.routes.structure.httpx.AsyncClient", fake_async_client):
        r = client.get("/api/v1/structure/jobs/legacy-1")
    assert r.status_code == 200
    assert r.json()["status"] == "running"

    db_session.expire_all()
    row = db_session.get(PredictionJob, "legacy-1")
    assert row is not None
    assert row.service == "esm"
    assert row.model_name == "unknown"
    assert row.last_status == "running"


def test_list_jobs_returns_recent_jobs(client, db_session):
    db_session.add_all(
        [
            PredictionJob(
                id=f"job-{i}",
                service="protenix",
                model_name="protenix_base_default_v1.0.0",
                request_json={"name": f"job-{i}"},
                last_status="completed",
            )
            for i in range(3)
        ]
    )
    db_session.commit()

    r = client.get("/api/v1/structure/jobs")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3
    assert {j["job_id"] for j in body} == {"job-0", "job-1", "job-2"}
    assert all(j["service"] == "protenix" for j in body)


def test_status_404_when_neither_worker_knows_job(client, db_session):
    err = _mock_response(404, {"detail": "Job not found"})
    fake_async_client = _async_client_returning({"get": [err, err]})
    with patch("app.routes.structure.httpx.AsyncClient", fake_async_client):
        r = client.get("/api/v1/structure/jobs/does-not-exist")
    assert r.status_code == 404
    assert db_session.get(PredictionJob, "does-not-exist") is None


@pytest.mark.parametrize("model,expected_service", [
    ("protenix_base_default_v1.0.0", "protenix"),
    ("protenix_mini_default_v0.5.0", "protenix"),
    ("esmfold_v1", "esm"),
    ("unknown_xyz", "protenix"),  # default fallback
])
def test_service_resolution(model, expected_service):
    from app.routes.structure import _resolve_service
    assert _resolve_service(model) == expected_service
