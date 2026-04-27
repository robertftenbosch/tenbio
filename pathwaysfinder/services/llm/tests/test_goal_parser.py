"""Tests for the LLM goal-parsing endpoint.

These tests mock Ollama with patched httpx responses so they can run on
CI without a GPU or any model pulled. The five validation queries from
the plan (§9) appear here as fixtures — when we wire up a real
end-to-end test against a running Gemma model later, the same query
strings should be reusable.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _mock_ollama_chat(content: str | dict):
    """Build an AsyncMock that replaces OllamaClient.chat.

    Accepts either a string (used verbatim as message.content) or a dict
    (json-serialized into message.content, mimicking format=json mode).
    """
    if isinstance(content, dict):
        content = json.dumps(content)
    fake_response = {"message": {"role": "assistant", "content": content}}
    return AsyncMock(return_value=fake_response)


# ---------------------------------------------------------------------------
# Validation query fixtures (matching docs/llm-service-plan.md §9)
# ---------------------------------------------------------------------------


@pytest.fixture
def query_ammonia():
    return {
        "query": "Maak een organisme dat uit mest de ammoniak haalt en omzet naar N2",
        "candidate_kegg_ids": [
            {"id": "cpd:C00014", "name": "Ammonia", "synonyms": ["NH3"]},
            {"id": "cpd:C00697", "name": "Nitrite", "synonyms": ["NO2-"]},
        ],
        "candidate_uniprot_ids": [],
    }


@pytest.fixture
def query_cheese():
    return {
        "query": "Maak de eiwitten om kaas te produceren",
        "candidate_kegg_ids": [],
        "candidate_uniprot_ids": [
            {"accession": "P02662", "name": "alpha-S1-casein", "organism": "Bos taurus"},
            {"accession": "P00794", "name": "Chymosin", "organism": "Bos taurus"},
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_when_ollama_unreachable(client):
    """If Ollama is down, /health reports degraded but does not 500."""
    with patch("app.main._client") as mock:
        mock.health = AsyncMock(return_value=False)
        mock.is_model_present = AsyncMock(return_value=False)
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama_reachable"] is False
    assert body["status"] == "degraded"
    assert body["model_loaded"] is False


def test_goal_parse_ammonia_returns_valid_intent(client, query_ammonia):
    expected_intent = {
        "raw_query": query_ammonia["query"],
        "target": {
            "kind": "removal",
            "name": "Ammonia (NH3) → N2",
            "kegg_id": "cpd:C00014",
            "uniprot_id": None,
            "smiles": None,
        },
        "host_candidates": [
            "Kuenenia stuttgartiensis",
            "Brocadia anammoxidans",
            "engineered E. coli",
        ],
        "optimization_metric": "rate",
        "constraints": ["agricultural-runoff context"],
        "feasibility_note": "Anammox bacteria perform anaerobic NH4+ + NO2- → N2 oxidation, but doubling time is ~11 days.",
        "confidence": "medium",
    }

    with patch("app.main._client.chat", _mock_ollama_chat(expected_intent)):
        r = client.post("/goal/parse", json=query_ammonia)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"]["target"]["kegg_id"] == "cpd:C00014"
    assert body["intent"]["target"]["kind"] == "removal"
    assert body["intent"]["confidence"] == "medium"
    assert "doubling time" in body["intent"]["feasibility_note"]


def test_goal_parse_cheese_recommends_yeast_not_bacteria(client, query_cheese):
    """Bacteria can't phosphorylate caseins -- LLM must point to fungi/yeast."""
    expected_intent = {
        "raw_query": query_cheese["query"],
        "target": {
            "kind": "protein",
            "name": "Caseins (αs1, αs2, β, κ) and chymosin",
            "kegg_id": None,
            "uniprot_id": "P02662",
            "smiles": None,
        },
        "host_candidates": [
            "Trichoderma reesei",
            "Pichia pastoris",
            "Kluyveromyces lactis",
            "Aspergillus niger",
        ],
        "optimization_metric": "titer",
        "constraints": ["food-grade", "secretion-competent host"],
        "feasibility_note": "Bacterial chassis cannot phosphorylate caseins correctly, so micelle formation fails.",
        "confidence": "high",
    }

    with patch("app.main._client.chat", _mock_ollama_chat(expected_intent)):
        r = client.post("/goal/parse", json=query_cheese)

    assert r.status_code == 200, r.text
    body = r.json()
    hosts = body["intent"]["host_candidates"]
    assert "Pichia pastoris" in hosts
    assert all("E. coli" not in h for h in hosts), "bacteria are wrong for caseins"
    assert "phosphorylate" in body["intent"]["feasibility_note"].lower()


def test_goal_parse_strips_hallucinated_kegg_ids(client, query_ammonia):
    """If the LLM produces a KEGG ID not in the candidate list, null it."""
    intent_with_hallucination = {
        "raw_query": query_ammonia["query"],
        "target": {
            "kind": "removal",
            "name": "Some made-up compound",
            "kegg_id": "cpd:C99999",  # NOT in query_ammonia candidates
            "uniprot_id": None,
            "smiles": None,
        },
        "host_candidates": ["E. coli"],
        "optimization_metric": "rate",
        "constraints": [],
        "feasibility_note": "n/a",
        "confidence": "low",
    }

    with patch("app.main._client.chat", _mock_ollama_chat(intent_with_hallucination)):
        r = client.post("/goal/parse", json=query_ammonia)

    assert r.status_code == 200
    assert r.json()["intent"]["target"]["kegg_id"] is None


def test_goal_parse_strips_hallucinated_uniprot_ids(client, query_cheese):
    intent_with_hallucination = {
        "raw_query": query_cheese["query"],
        "target": {
            "kind": "protein",
            "name": "x",
            "kegg_id": None,
            "uniprot_id": "Z99999",  # NOT in candidates
            "smiles": None,
        },
        "host_candidates": ["P. pastoris"],
        "optimization_metric": "titer",
        "constraints": [],
        "feasibility_note": "n/a",
        "confidence": "low",
    }

    with patch("app.main._client.chat", _mock_ollama_chat(intent_with_hallucination)):
        r = client.post("/goal/parse", json=query_cheese)

    assert r.status_code == 200
    assert r.json()["intent"]["target"]["uniprot_id"] is None


def test_goal_parse_502_on_invalid_json(client, query_ammonia):
    """The LLM returned text that isn't JSON -- must error cleanly."""
    with patch("app.main._client.chat", _mock_ollama_chat("I'm sorry, I can't help with that.")):
        r = client.post("/goal/parse", json=query_ammonia)
    assert r.status_code == 502
    assert "valid JSON" in r.json()["detail"]


def test_goal_parse_502_on_schema_mismatch(client, query_ammonia):
    """LLM returned valid JSON but missing required fields."""
    with patch(
        "app.main._client.chat",
        _mock_ollama_chat({"target": {"kind": "compound", "name": "x"}}),
    ):
        r = client.post("/goal/parse", json=query_ammonia)
    assert r.status_code == 502
    assert "DesignIntent" in r.json()["detail"]


def test_goal_parse_503_when_ollama_down(client, query_ammonia):
    err = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    with patch("app.main._client.chat", err):
        r = client.post("/goal/parse", json=query_ammonia)
    assert r.status_code == 503
    assert "Ollama" in r.json()["detail"]


def test_chat_endpoint_returns_content(client):
    fake_response = {"message": {"role": "assistant", "content": "Ja, dat klopt."}}
    with patch("app.main._client.chat", AsyncMock(return_value=fake_response)):
        r = client.post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "Hallo, werk je?"}],
                "temperature": 0.1,
                "max_tokens": 256,
            },
        )
    assert r.status_code == 200
    assert r.json()["content"] == "Ja, dat klopt."
