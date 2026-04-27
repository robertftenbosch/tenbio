"""Flux Balance Analysis via cobrapy.

This is the deterministic engine for "given a pathway in a chassis, what
production rate can we expect?" It builds on a registry of genome-scale
models. v1 ships with cobra's bundled `textbook` (E. coli core, 95
reactions) and exposes a thin wrapper around `Model.optimize()` plus
knockout / overexpression simulation.

Bigger genome-scale models (iML1515 for E. coli K-12, iMM904 for
S. cerevisiae, etc.) live as SBML files under data/models/ and load
on demand. They're not in this PR; the registry is built so adding
one is a single dict entry.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import cobra
import cobra.io

logger = logging.getLogger(__name__)


# --- Model registry --------------------------------------------------------


@dataclass(frozen=True)
class ChassisModel:
    """Metadata for a genome-scale metabolic model."""

    key: str               # short name used in the API ("textbook", "iML1515", ...)
    description: str
    organism: str          # human-readable
    kegg_organism: str     # KEGG code, e.g. "eco"
    domain: str            # bacterial | fungal | photosynthetic | mammalian
    n_reactions: int       # approximate, for UI display
    biomass_objective: str  # biomass reaction id


# Path where future SBML models will live. Mounted as a docker volume so
# big models don't bloat the image.
DATA_MODELS_DIR = os.environ.get(
    "FBA_MODELS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "models"),
)


CHASSIS_REGISTRY: dict[str, ChassisModel] = {
    "textbook": ChassisModel(
        key="textbook",
        description="E. coli core model (cobrapy bundled, ~95 rxns). Fast, ideal for development and tests.",
        organism="Escherichia coli (core)",
        kegg_organism="eco",
        domain="bacterial",
        n_reactions=95,
        biomass_objective="Biomass_Ecoli_core",
    ),
    # Larger models drop in by adding an entry + the SBML file under
    # DATA_MODELS_DIR. Phase 3 (chassis expansion) populates the rest.
    # "iML1515": ChassisModel(...),
    # "iMM904":  ChassisModel(...),
    # "iSynCJ816": ChassisModel(...),
}


def list_chassis() -> list[dict]:
    """API-friendly summary of available chassis models."""
    out = []
    for cm in CHASSIS_REGISTRY.values():
        out.append(
            {
                "key": cm.key,
                "description": cm.description,
                "organism": cm.organism,
                "kegg_organism": cm.kegg_organism,
                "domain": cm.domain,
                "n_reactions": cm.n_reactions,
                "biomass_objective": cm.biomass_objective,
            }
        )
    return out


@lru_cache(maxsize=4)
def _load_model_cached(key: str) -> cobra.Model:
    """Load a chassis model once and reuse. cobra.Model is mutable; callers
    must `with model:` clone before changing bounds, or call _fresh_copy()."""
    if key not in CHASSIS_REGISTRY:
        raise KeyError(f"Unknown chassis '{key}'. Known: {list(CHASSIS_REGISTRY)}")

    if key == "textbook":
        return cobra.io.load_model("textbook")

    sbml_path = os.path.join(DATA_MODELS_DIR, f"{key}.xml")
    if not os.path.isfile(sbml_path):
        raise FileNotFoundError(
            f"SBML for chassis '{key}' not found at {sbml_path}. "
            f"Add the model to {DATA_MODELS_DIR}/ to enable it."
        )
    return cobra.io.read_sbml_model(sbml_path)


def get_model(key: str) -> cobra.Model:
    """Return a fresh copy of the cached model for safe mutation."""
    base = _load_model_cached(key)
    return base.copy()


# --- FBA core --------------------------------------------------------------


@dataclass
class FBAResult:
    chassis: str
    objective_id: str
    objective_value: float
    growth_rate: float
    target_reaction: Optional[str]
    target_flux: Optional[float]
    status: str
    fluxes: list[dict]
    notes: list[str]


def _set_carbon_source(
    model: cobra.Model, exchange_id: str, uptake: float, notes: list[str]
) -> None:
    """Close all carbon-source exchanges except the chosen one and pin its uptake.

    `uptake` is signed: negative for consumption (the cobra convention).
    """
    if exchange_id not in model.reactions:
        notes.append(
            f"Carbon source '{exchange_id}' not in model; carbon source change skipped."
        )
        return
    # Close existing C-source exchanges. Heuristic: any exchange whose name
    # mentions glucose / fructose / xylose / acetate that is currently open
    # for uptake gets closed.
    carbon_keywords = ("glc", "fru", "xyl", "ac", "succ", "pyr", "lac")
    for rxn in model.exchanges:
        if any(k in rxn.id.lower() for k in carbon_keywords):
            if rxn.id != exchange_id and rxn.lower_bound < 0:
                rxn.lower_bound = 0.0
    target = model.reactions.get_by_id(exchange_id)
    target.lower_bound = uptake


def _apply_knockouts(
    model: cobra.Model, knockouts: list[str], notes: list[str]
) -> None:
    for rid in knockouts:
        if rid not in model.reactions:
            notes.append(f"Knockout '{rid}' not in model; skipped.")
            continue
        model.reactions.get_by_id(rid).bounds = (0.0, 0.0)


def _set_objective(
    model: cobra.Model, objective: str, target_reaction: Optional[str], notes: list[str]
) -> str:
    """Decide what the solver maximises. Returns the resolved objective id."""
    if objective == "biomass":
        # Trust the model's current objective; cobra ships textbook with
        # biomass already set.
        objective_ids = [
            r.id for r in model.reactions if model.objective.expression.has(r.flux_expression)
        ]
        return objective_ids[0] if objective_ids else "Biomass_Ecoli_core"
    if objective == "target":
        if not target_reaction:
            raise ValueError("objective='target' requires target_reaction.")
        if target_reaction not in model.reactions:
            raise ValueError(
                f"target_reaction '{target_reaction}' not in chassis model."
            )
        model.objective = target_reaction
        return target_reaction
    raise ValueError(f"Unknown objective '{objective}'.")


def run_fba(
    chassis: str,
    *,
    target_reaction: Optional[str] = None,
    knockouts: Optional[list[str]] = None,
    objective: str = "biomass",
    carbon_source: Optional[str] = None,
    carbon_uptake: float = -10.0,
    flux_limit: int = 25,
) -> FBAResult:
    """Run FBA on the chassis with optional knockouts and carbon-source override.

    `flux_limit` caps the per-reaction flux array we send back to keep
    response payloads small; full flux distribution is paginatable in a
    later iteration.
    """
    knockouts = knockouts or []
    notes: list[str] = []

    model = get_model(chassis)

    if carbon_source is not None:
        _set_carbon_source(model, carbon_source, carbon_uptake, notes)

    _apply_knockouts(model, knockouts, notes)

    objective_id = _set_objective(model, objective, target_reaction, notes)

    solution = model.optimize()

    growth_rate = 0.0
    biomass_id = CHASSIS_REGISTRY[chassis].biomass_objective
    if biomass_id in model.reactions:
        try:
            growth_rate = float(solution.fluxes.get(biomass_id, 0.0) or 0.0)
        except Exception:
            pass

    target_flux = None
    if target_reaction and target_reaction in solution.fluxes.index:
        target_flux = float(solution.fluxes[target_reaction])

    # Top-N reactions by absolute flux magnitude — most informative slice.
    fluxes_pairs = sorted(
        (
            (rid, float(val))
            for rid, val in solution.fluxes.items()
            if val is not None
        ),
        key=lambda kv: abs(kv[1]),
        reverse=True,
    )[:flux_limit]
    fluxes = []
    for rid, val in fluxes_pairs:
        rxn = model.reactions.get_by_id(rid)
        fluxes.append(
            {
                "reaction_id": rid,
                "flux": val,
                "lower_bound": float(rxn.lower_bound),
                "upper_bound": float(rxn.upper_bound),
                "name": rxn.name or None,
            }
        )

    obj_value = float(solution.objective_value or 0.0)

    if solution.status != "optimal":
        notes.append(f"Solver status: {solution.status}.")

    return FBAResult(
        chassis=chassis,
        objective_id=objective_id,
        objective_value=obj_value,
        growth_rate=growth_rate,
        target_reaction=target_reaction,
        target_flux=target_flux,
        status=solution.status,
        fluxes=fluxes,
        notes=notes,
    )
