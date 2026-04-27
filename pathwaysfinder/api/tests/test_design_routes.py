"""Tests for /api/v1/design — the natural-language design routes.

LLM service is mocked; KEGG / UniProt grounding is mocked at the helper
level so the tests don't touch the network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def ammonia_llm_response():
    return {
        "intent": {
            "raw_query": "Maak een organisme dat ammoniak afbreekt naar N2",
            "target": {
                "kind": "removal",
                "name": "Ammonia",
                "kegg_id": "cpd:C00014",
                "uniprot_id": None,
                "smiles": None,
            },
            "host_candidates": ["Kuenenia", "engineered E. coli"],
            "optimization_metric": "rate",
            "constraints": ["agricultural-runoff context"],
            "feasibility_note": "Anammox is real but slow.",
            "confidence": "medium",
        },
        "model_used": "gemma3:9b",
        "raw_llm_output": "{...}",
    }


def test_from_goal_grounds_then_calls_llm(client, ammonia_llm_response):
    """Happy path: grounding produces candidates, LLM is called with them."""
    fake_candidates = (
        [{"id": "cpd:C00014", "name": "Ammonia", "synonyms": ["NH3"]}],
        [],
    )

    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=fake_candidates),
    ), patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ) as parse_mock:
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak een organisme dat ammoniak afbreekt naar N2"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"]["target"]["kegg_id"] == "cpd:C00014"
    assert body["candidate_kegg_count"] == 1
    assert body["candidate_uniprot_count"] == 0
    assert body["model_used"] == "gemma3:9b"

    # The LLM client should have been called with the grounded candidates.
    parse_mock.assert_called_once()
    call_kwargs = parse_mock.call_args.kwargs
    assert call_kwargs["candidate_kegg_ids"] == [
        {"id": "cpd:C00014", "name": "Ammonia", "synonyms": ["NH3"]}
    ]


def test_from_goal_skip_grounding_passes_empty_candidates(client, ammonia_llm_response):
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([{"id": "cpd:C00014", "name": "Ammonia"}], [])),
    ) as ground_mock, patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ) as parse_mock:
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Test query that should skip grounding", "skip_grounding": True},
        )

    assert r.status_code == 200
    # build_candidates should NOT have been called
    ground_mock.assert_not_called()
    # LLM should still be called, but with empty candidate lists
    assert parse_mock.call_args.kwargs["candidate_kegg_ids"] == []


def test_from_goal_503_when_llm_unreachable(client):
    from app.external_apis.llm_client import LLMServiceError

    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([], [])),
    ), patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(side_effect=LLMServiceError("LLM service unreachable")),
    ):
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak iets nieuws"},
        )

    assert r.status_code == 503
    assert "unreachable" in r.json()["detail"]


def test_from_goal_rejects_short_query(client):
    r = client.post("/api/v1/design/from-goal", json={"query": "ai"})
    assert r.status_code == 422


def test_from_compound_returns_501(client):
    """Stub endpoint until the next PR."""
    r = client.post("/api/v1/design/from-compound")
    assert r.status_code == 501
    assert "follow-up" in r.json()["detail"].lower() or "next pr" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# goal_grounding helper
# ---------------------------------------------------------------------------


def test_grounding_extracts_dutch_substance_keywords():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("haal de ammoniak uit mest en maak er N2 van")
    assert "ammonia" in cpd
    assert prot == [] or all(p != "ammonia" for p in prot)


def test_grounding_routes_protein_keywords_to_uniprot():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("Maak de eiwitten om kaas te produceren")
    # "kaas" -> "casein" goes to protein bucket because casein is a protein
    assert "casein" in prot
    assert "casein" not in cpd


def test_grounding_falls_back_to_longest_token():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("foobarbazquux")
    assert cpd == ["foobarbazquux"]
    assert prot == []
