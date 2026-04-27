"""Tests for /api/v1/simulate/* — FBA via cobrapy.

Uses cobra's bundled `textbook` E. coli core model so the suite has no
external SBML dependency. The model has well-known steady-state behavior
which lets us assert on concrete numbers (biomass ~0.87 with default
glucose uptake; ATPM and biomass active in the optimal solution).
"""

from __future__ import annotations

import pytest

from app.services import fba


# ---------------------------------------------------------------------------
# /chassis listing
# ---------------------------------------------------------------------------


def test_list_chassis_returns_textbook(client):
    r = client.get("/api/v1/simulate/chassis")
    assert r.status_code == 200
    body = r.json()
    keys = [c["key"] for c in body]
    assert "textbook" in keys
    textbook = next(c for c in body if c["key"] == "textbook")
    assert textbook["domain"] == "bacterial"
    assert textbook["kegg_organism"] == "eco"
    assert textbook["n_reactions"] >= 90


# ---------------------------------------------------------------------------
# /fba — happy paths
# ---------------------------------------------------------------------------


def test_fba_default_biomass_optimum(client):
    """Textbook E. coli core grows at ~0.87 /h on the default glucose uptake."""
    r = client.post("/api/v1/simulate/fba", json={"chassis": "textbook"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "optimal"
    assert body["chassis"] == "textbook"
    # Biomass is in the [0.85, 0.90] range for the textbook model with
    # default media. Loose bounds because solver-version drift can shift
    # the third decimal.
    assert 0.85 <= body["growth_rate"] <= 0.90
    assert body["objective_value"] == pytest.approx(body["growth_rate"], abs=0.001)
    # Top fluxes should include the biomass reaction.
    rxn_ids = {f["reaction_id"] for f in body["fluxes"]}
    assert any("Biomass" in r for r in rxn_ids) or "ATPM" in rxn_ids


def test_fba_target_objective_maximises_target(client):
    """Switching the objective to ethanol export should put non-zero flux on it."""
    r = client.post(
        "/api/v1/simulate/fba",
        json={
            "chassis": "textbook",
            "objective": "target",
            "target_reaction": "EX_etoh_e",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "optimal"
    assert body["target_reaction"] == "EX_etoh_e"
    assert body["target_flux"] is not None
    # With biomass no longer the objective, the solver finds the maximum
    # ethanol export — empirically > 0 in the textbook model.
    assert body["target_flux"] > 0
    assert body["objective_value"] == pytest.approx(body["target_flux"], abs=0.01)


def test_fba_knockout_reduces_growth(client):
    """Knocking out a central-carbon reaction (PFK) drops biomass below wild-type."""
    wt = client.post("/api/v1/simulate/fba", json={"chassis": "textbook"}).json()
    ko = client.post(
        "/api/v1/simulate/fba",
        json={"chassis": "textbook", "knockouts": ["PFK"]},
    ).json()
    assert ko["status"] == "optimal"
    assert ko["growth_rate"] < wt["growth_rate"]


def test_fba_carbon_source_override_changes_growth(client):
    """Switching glucose to acetate should yield a clearly different (lower) growth rate."""
    glucose = client.post(
        "/api/v1/simulate/fba",
        json={"chassis": "textbook"},
    ).json()
    acetate = client.post(
        "/api/v1/simulate/fba",
        json={
            "chassis": "textbook",
            "carbon_source": "EX_ac_e",
            "carbon_uptake": -10.0,
        },
    ).json()
    assert acetate["status"] == "optimal"
    # Acetate is a worse carbon source than glucose for E. coli core.
    assert acetate["growth_rate"] < glucose["growth_rate"]


# ---------------------------------------------------------------------------
# /fba — error paths
# ---------------------------------------------------------------------------


def test_fba_unknown_chassis_returns_404(client):
    r = client.post("/api/v1/simulate/fba", json={"chassis": "definitely-not-a-model"})
    assert r.status_code == 404
    assert "Unknown chassis" in r.json()["detail"]


def test_fba_target_without_reaction_returns_422(client):
    r = client.post(
        "/api/v1/simulate/fba",
        json={"chassis": "textbook", "objective": "target"},
    )
    assert r.status_code == 422


def test_fba_target_reaction_not_in_model_returns_422(client):
    r = client.post(
        "/api/v1/simulate/fba",
        json={
            "chassis": "textbook",
            "objective": "target",
            "target_reaction": "NOT_A_REAL_REACTION",
        },
    )
    assert r.status_code == 422


def test_fba_unknown_knockout_emits_note(client):
    """Unknown knockout names shouldn't fail; they're surfaced as a note."""
    r = client.post(
        "/api/v1/simulate/fba",
        json={"chassis": "textbook", "knockouts": ["NOT_REAL"]},
    )
    assert r.status_code == 200
    assert any("NOT_REAL" in n for n in r.json()["notes"])


# ---------------------------------------------------------------------------
# Service-level (no FastAPI)
# ---------------------------------------------------------------------------


def test_get_model_returns_independent_copy():
    """Mutating one returned copy must not leak into the next."""
    a = fba.get_model("textbook")
    b = fba.get_model("textbook")
    a.reactions.PFK.bounds = (0.0, 0.0)
    assert b.reactions.PFK.bounds != (0.0, 0.0)


def test_run_fba_flux_limit_caps_response():
    result = fba.run_fba("textbook", flux_limit=5)
    assert len(result.fluxes) == 5
    # Sorted by |flux| descending.
    abs_fluxes = [abs(f["flux"]) for f in result.fluxes]
    assert abs_fluxes == sorted(abs_fluxes, reverse=True)
