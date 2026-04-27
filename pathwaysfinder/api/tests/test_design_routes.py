"""Tests for /api/v1/design — natural-language and compound-driven routes.

External services (LLM, KEGG, UniProt) are mocked so the suite has no
network or GPU dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


@pytest.fixture
def fake_search_result():
    """Minimal pathway_search.search_pathway return shape."""
    return {
        "target": {"id": "cpd:C00014", "name": "Ammonia"},
        "host": "eco",
        "max_depth_used": 2,
        "reactions": [
            {
                "reaction_id": "rn:R00253",
                "reaction_name": "Glutamine synthetase",
                "equation": "C00025 + C00014 + C00002 <=> C00064 + C00008 + C00009",
                "ec_numbers": ["6.3.1.2"],
                "substrates": ["cpd:C00025", "cpd:C00014", "cpd:C00002"],
                "products": ["cpd:C00064", "cpd:C00008", "cpd:C00009"],
                "candidate_genes": [
                    {
                        "id": "eco:b3870",
                        "name": "glnA",
                        "definition": "glutamine synthetase",
                        "organism": "Escherichia coli",
                        "ec_number": "6.3.1.2",
                    }
                ],
                "depth": 0,
            }
        ],
        "notes": [],
    }


# ---------------------------------------------------------------------------
# /from-goal happy paths
# ---------------------------------------------------------------------------


def test_from_goal_grounds_then_calls_llm(client, ammonia_llm_response, fake_search_result):
    """Default materialize=true chains to /from-compound after the LLM call."""
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([{"id": "cpd:C00014", "name": "Ammonia"}], [])),
    ), patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ) as parse_mock, patch(
        "app.routes.design.pathway_search.search_pathway",
        AsyncMock(return_value=fake_search_result),
    ) as search_mock:
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak een organisme dat ammoniak afbreekt naar N2"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"]["target"]["kegg_id"] == "cpd:C00014"
    assert body["candidate_kegg_count"] == 1
    assert body["pathway_candidates"] is not None
    assert body["pathway_candidates"]["target"]["id"] == "cpd:C00014"
    assert body["pathway_candidates"]["reactions"][0]["candidate_genes"][0]["name"] == "glnA"
    parse_mock.assert_called_once()
    search_mock.assert_called_once()


def test_from_goal_skip_materialize(client, ammonia_llm_response):
    """materialize=false returns intent only, no KEGG search."""
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([], [])),
    ), patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ), patch(
        "app.routes.design.pathway_search.search_pathway", AsyncMock()
    ) as search_mock:
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak iets cools", "materialize": False},
        )

    assert r.status_code == 200
    assert r.json()["pathway_candidates"] is None
    search_mock.assert_not_called()


def test_from_goal_no_kegg_id_skips_materialize(client):
    """If LLM returns a target without a kegg_id, materialization is skipped."""
    no_kegg_response = {
        "intent": {
            "raw_query": "Make some protein",
            "target": {
                "kind": "protein",
                "name": "x",
                "kegg_id": None,
                "uniprot_id": "P02662",
                "smiles": None,
            },
            "host_candidates": ["P. pastoris"],
            "optimization_metric": "titer",
            "constraints": [],
            "feasibility_note": "ok",
            "confidence": "high",
        },
        "model_used": "gemma3:9b",
    }
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([], [])),
    ), patch(
        "app.routes.design.llm_client.parse_goal", AsyncMock(return_value=no_kegg_response)
    ), patch(
        "app.routes.design.pathway_search.search_pathway", AsyncMock()
    ) as search_mock:
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Make a fancy protein"},
        )
    assert r.status_code == 200
    assert r.json()["pathway_candidates"] is None
    search_mock.assert_not_called()


def test_from_goal_skip_grounding_passes_empty_candidates(client, ammonia_llm_response):
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([{"id": "cpd:C00014", "name": "Ammonia"}], [])),
    ) as ground_mock, patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ) as parse_mock, patch(
        "app.routes.design.pathway_search.search_pathway", AsyncMock()
    ):
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak iets nieuws", "skip_grounding": True, "materialize": False},
        )

    assert r.status_code == 200
    ground_mock.assert_not_called()
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
            json={"query": "Maak iets nieuws", "materialize": False},
        )

    assert r.status_code == 503
    assert "unreachable" in r.json()["detail"]


def test_from_goal_rejects_short_query(client):
    r = client.post("/api/v1/design/from-goal", json={"query": "ai"})
    assert r.status_code == 422


def test_from_goal_materialization_failure_keeps_intent(client, ammonia_llm_response):
    """If KEGG flakes during materialization, return the intent without it."""
    with patch(
        "app.routes.design.goal_grounding.build_candidates",
        AsyncMock(return_value=([{"id": "cpd:C00014", "name": "Ammonia"}], [])),
    ), patch(
        "app.routes.design.llm_client.parse_goal",
        AsyncMock(return_value=ammonia_llm_response),
    ), patch(
        "app.routes.design.pathway_search.search_pathway",
        AsyncMock(side_effect=RuntimeError("KEGG timeout")),
    ):
        r = client.post(
            "/api/v1/design/from-goal",
            json={"query": "Maak een organisme dat ammoniak afbreekt"},
        )
    assert r.status_code == 200
    assert r.json()["pathway_candidates"] is None
    assert r.json()["intent"]["target"]["kegg_id"] == "cpd:C00014"


# ---------------------------------------------------------------------------
# /from-compound
# ---------------------------------------------------------------------------


def test_from_compound_returns_reactions(client, fake_search_result):
    with patch(
        "app.routes.design.pathway_search.resolve_compound_id",
        AsyncMock(return_value="cpd:C00014"),
    ), patch(
        "app.routes.design.pathway_search.search_pathway",
        AsyncMock(return_value=fake_search_result),
    ):
        r = client.post(
            "/api/v1/design/from-compound",
            json={"compound": "ammonia", "host": "eco", "max_depth": 1},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target"]["id"] == "cpd:C00014"
    assert body["host"] == "eco"
    assert len(body["reactions"]) == 1
    rxn = body["reactions"][0]
    assert rxn["depth"] == 0
    assert rxn["ec_numbers"] == ["6.3.1.2"]
    assert rxn["candidate_genes"][0]["name"] == "glnA"


def test_from_compound_404_when_unresolvable(client):
    with patch(
        "app.routes.design.pathway_search.resolve_compound_id", AsyncMock(return_value=None)
    ):
        r = client.post(
            "/api/v1/design/from-compound",
            json={"compound": "definitely-not-a-real-compound-zxy"},
        )
    assert r.status_code == 404
    assert "KEGG" in r.json()["detail"]


def test_from_compound_accepts_kegg_id_directly(client, fake_search_result):
    """A query that's already a KEGG ID should skip the search step."""
    with patch(
        "app.routes.design.pathway_search.resolve_compound_id",
        AsyncMock(return_value="cpd:C00014"),
    ) as resolve_mock, patch(
        "app.routes.design.pathway_search.search_pathway",
        AsyncMock(return_value=fake_search_result),
    ):
        r = client.post(
            "/api/v1/design/from-compound",
            json={"compound": "cpd:C00014"},
        )
    assert r.status_code == 200
    resolve_mock.assert_called_once_with("cpd:C00014")


def test_from_compound_rejects_too_short(client):
    r = client.post("/api/v1/design/from-compound", json={"compound": "x"})
    assert r.status_code == 422


def test_from_compound_caps_max_depth(client):
    r = client.post(
        "/api/v1/design/from-compound",
        json={"compound": "ammonia", "max_depth": 99},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# pathway_search internals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_compound_id_normalises_kegg_id():
    from app.services.pathway_search import resolve_compound_id

    assert await resolve_compound_id("cpd:C00014") == "cpd:C00014"
    assert await resolve_compound_id("C00014") == "cpd:C00014"


@pytest.mark.asyncio
async def test_resolve_compound_id_falls_back_to_search():
    from app.services import pathway_search

    with patch(
        "app.services.pathway_search.search_compounds",
        AsyncMock(return_value=[{"id": "cpd:C00014", "name": "Ammonia"}]),
    ):
        assert await pathway_search.resolve_compound_id("ammonia") == "cpd:C00014"


@pytest.mark.asyncio
async def test_resolve_compound_id_returns_none_on_no_hit():
    from app.services import pathway_search

    with patch(
        "app.services.pathway_search.search_compounds", AsyncMock(return_value=[])
    ):
        assert await pathway_search.resolve_compound_id("nonsense") is None


@pytest.mark.asyncio
async def test_search_pathway_handles_unknown_compound():
    from app.services import pathway_search

    with patch(
        "app.services.pathway_search.get_compound_info", AsyncMock(return_value=None)
    ):
        result = await pathway_search.search_pathway("cpd:C99999", max_depth=1)
    assert result["reactions"] == []
    assert any("not found" in n.lower() for n in result["notes"])


@pytest.mark.asyncio
async def test_search_pathway_collects_direct_producers():
    """Depth=0: target compound has 1 reaction; substrate is non-hub."""
    from app.services import pathway_search

    target = {
        "id": "cpd:C00014",
        "name": "Ammonia",
        "reaction_ids": ["rn:R00253"],
        "pathway_ids": [],
        "enzyme_ec": ["6.3.1.2"],
    }
    glutamate = {
        "id": "cpd:C00025",
        "name": "L-Glutamate",
        "reaction_ids": [],
        "pathway_ids": [],
        "enzyme_ec": [],
    }
    rxn = {
        "id": "rn:R00253",
        "name": "GS",
        "equation": "C00025 + C00014 <=> C00064",
        "left_compounds": ["cpd:C00025", "cpd:C00014"],
        "right_compounds": ["cpd:C00064"],
        "ec_numbers": ["6.3.1.2"],
    }
    gene = {"id": "eco:b3870", "name": "glnA"}

    async def fake_compound_info(cpd_id):
        return {
            "cpd:C00014": target,
            "cpd:C00025": glutamate,
        }.get(cpd_id)

    with patch(
        "app.services.pathway_search.get_compound_info",
        AsyncMock(side_effect=fake_compound_info),
    ), patch(
        "app.services.pathway_search.get_reaction_info", AsyncMock(return_value=rxn)
    ), patch(
        "app.services.pathway_search.get_enzyme_genes", AsyncMock(return_value=[gene])
    ):
        result = await pathway_search.search_pathway(
            "cpd:C00014", host_organism="eco", max_depth=0
        )

    assert len(result["reactions"]) == 1
    step = result["reactions"][0]
    assert step["depth"] == 0
    assert step["candidate_genes"][0]["name"] == "glnA"
    # The target (C00014) is on the left side of the reaction, so the
    # retrosynthetic "substrates" (i.e. what we'd need to start from to
    # produce C00014 by running the reaction in reverse) come from the
    # right side: C00064 (glutamine).
    assert step["substrates"] == ["cpd:C00064"]
    assert "cpd:C00014" in step["products"]


@pytest.mark.asyncio
async def test_search_pathway_prunes_hub_metabolites():
    """ATP / water on the substrate side must not be expanded."""
    from app.services import pathway_search

    target = {
        "id": "cpd:C99999",
        "name": "Target",
        "reaction_ids": ["rn:R12345"],
        "pathway_ids": [],
        "enzyme_ec": ["1.1.1.1"],
    }
    rxn = {
        "id": "rn:R12345",
        "name": "X synthase",
        "equation": "C00002 + C00001 <=> C99999 + C00008",
        "left_compounds": ["cpd:C00002", "cpd:C00001"],   # ATP + H2O (hubs)
        "right_compounds": ["cpd:C99999", "cpd:C00008"],
        "ec_numbers": ["1.1.1.1"],
    }
    expanded: list[str] = []

    async def fake_compound_info(cpd_id):
        expanded.append(cpd_id)
        if cpd_id == "cpd:C99999":
            return target
        return {
            "id": cpd_id,
            "name": cpd_id,
            "reaction_ids": [],
            "pathway_ids": [],
            "enzyme_ec": [],
        }

    with patch(
        "app.services.pathway_search.get_compound_info",
        AsyncMock(side_effect=fake_compound_info),
    ), patch(
        "app.services.pathway_search.get_reaction_info", AsyncMock(return_value=rxn)
    ), patch(
        "app.services.pathway_search.get_enzyme_genes", AsyncMock(return_value=[])
    ):
        await pathway_search.search_pathway(
            "cpd:C99999", host_organism="eco", max_depth=2
        )

    # Hubs (ATP, H2O) should never be expanded as new BFS frontiers.
    assert "cpd:C00002" not in expanded
    assert "cpd:C00001" not in expanded


# ---------------------------------------------------------------------------
# goal_grounding helper (carried over from prior PR; ensures coverage)
# ---------------------------------------------------------------------------


def test_grounding_extracts_dutch_substance_keywords():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("haal de ammoniak uit mest en maak er N2 van")
    assert "ammonia" in cpd
    assert prot == [] or all(p != "ammonia" for p in prot)


def test_grounding_routes_protein_keywords_to_uniprot():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("Maak de eiwitten om kaas te produceren")
    assert "casein" in prot
    assert "casein" not in cpd


def test_grounding_falls_back_to_longest_token():
    from app.services.goal_grounding import _extract_keywords

    cpd, prot = _extract_keywords("foobarbazquux")
    assert cpd == ["foobarbazquux"]
    assert prot == []


# ---------------------------------------------------------------------------
# /chat/stream
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[dict]:
    import json as _json

    return [
        _json.loads(line[len("data: "):])
        for line in body.split("\n")
        if line.startswith("data: ")
    ]


def test_chat_stream_passes_through_token_events(client):
    """Stream chunks from the LLM service are forwarded verbatim to the client."""
    sse_chunks = [
        b'data: {"token": "Hallo"}\n\n',
        b'data: {"token": " wereld"}\n\n',
        b'data: {"done": true}\n\n',
    ]

    async def fake_stream(*_args, **_kwargs):
        for c in sse_chunks:
            yield c

    with patch(
        "app.routes.design.llm_client.stream_chat", fake_stream
    ):
        with client.stream(
            "POST",
            "/api/v1/design/chat/stream",
            json={"messages": [{"role": "user", "content": "Hallo"}]},
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = "".join(r.iter_text())

    events = _parse_sse(body)
    assert any(e.get("token") == "Hallo" for e in events)
    assert any(e.get("token") == " wereld" for e in events)
    assert any(e.get("done") is True for e in events)


def test_chat_stream_includes_intent_context(client, ammonia_llm_response):
    """When an intent is sent, the LLM gets a system message preamble for it."""
    captured: list[list[dict]] = []

    async def fake_stream(messages, **_kwargs):
        captured.append(messages)
        yield b'data: {"done": true}\n\n'

    with patch("app.routes.design.llm_client.stream_chat", fake_stream):
        with client.stream(
            "POST",
            "/api/v1/design/chat/stream",
            json={
                "messages": [{"role": "user", "content": "Waarom anammox?"}],
                "intent": ammonia_llm_response["intent"],
            },
        ) as r:
            list(r.iter_text())

    assert len(captured) == 1
    sent = captured[0]
    # Two system messages (base + intent), then user.
    assert sent[0]["role"] == "system"
    assert sent[1]["role"] == "system"
    assert "Anammox" in sent[1]["content"] or "anammox" in sent[1]["content"]
    assert "feasibility note" in sent[1]["content"].lower()
    assert sent[-1] == {"role": "user", "content": "Waarom anammox?"}


def test_chat_stream_emits_error_when_llm_unreachable(client):
    """LLMServiceError mid-stream surfaces as an SSE error+done pair."""
    from app.external_apis.llm_client import LLMServiceError

    async def fake_stream(*_args, **_kwargs):
        raise LLMServiceError("ollama down")
        yield b""  # unreachable; here so the function is async-iterable

    with patch("app.routes.design.llm_client.stream_chat", fake_stream):
        with client.stream(
            "POST",
            "/api/v1/design/chat/stream",
            json={"messages": [{"role": "user", "content": "x"}]},
        ) as r:
            assert r.status_code == 200
            body = "".join(r.iter_text())

    events = _parse_sse(body)
    assert any("ollama down" in (e.get("error") or "") for e in events)
    assert any(e.get("done") is True for e in events)
