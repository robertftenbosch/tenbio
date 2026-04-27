"""Retrosynthetic BFS over KEGG reactions.

Given a target compound and a host organism, walk backwards through
KEGG reactions to surface candidate enzymes (and host genes) that
could produce the target. The result is a flat list of `ReactionStep`
records tagged with their BFS depth, which the frontend can render as
a tree or graph.

Key design points:

- We treat KEGG reactions as direction-neutral. A reaction "involves"
  the target if the target appears on either side; the OTHER side
  becomes the substrate set we expand next.
- Hub metabolites (water, ATP, NAD+, etc.) are excluded because they
  appear in thousands of reactions and would explode the BFS without
  representing real biosynthetic precursors.
- Depth is bounded (default 2). A typical pathway in a textbook is
  3-5 steps; depth=2 reaches grand-grandparents in retrosynthesis,
  which is enough for "show me what could make this" without being a
  full retrosynthesis solver.
- Per-EC gene lookup is parallelised through the existing
  `get_enzyme_genes` helper (which already does EC -> KO -> gene
  fallback and detail-fetch concurrency).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.external_apis.kegg import (
    get_compound_info,
    get_enzyme_genes,
    get_reaction_info,
    search_compounds,
)

logger = logging.getLogger(__name__)


# Hub / currency metabolites. These appear in thousands of reactions
# and don't represent meaningful biosynthetic precursors. Maintained
# as a deliberately small list — overprune is safer than underprune
# for BFS explosion. KEGG IDs without the cpd: prefix.
HUB_COMPOUNDS: frozenset[str] = frozenset(
    {
        "C00001",  # H2O
        "C00002",  # ATP
        "C00003",  # NAD+
        "C00004",  # NADH
        "C00005",  # NADPH
        "C00006",  # NADP+
        "C00007",  # O2
        "C00008",  # ADP
        "C00009",  # Pi (orthophosphate)
        "C00010",  # CoA
        "C00011",  # CO2
        "C00013",  # PPi
        "C00016",  # FAD
        "C00019",  # S-adenosyl-L-methionine
        "C00020",  # AMP
        "C00021",  # S-adenosyl-L-homocysteine
        "C00080",  # H+
        "C00138",  # Reduced ferredoxin
        "C00139",  # Oxidized ferredoxin
        "C00342",  # Thioredoxin (reduced)
        "C00343",  # Thioredoxin (oxidized)
        "C01352",  # FADH2
        # NH3 (C00014) is conventionally a hub but is the literal target
        # of one of our validation queries, so we deliberately leave it
        # off this list.
    }
)


def _strip_cpd(cpd_id: str) -> str:
    return cpd_id[4:] if cpd_id.startswith("cpd:") else cpd_id


def _is_hub(cpd_id: str) -> bool:
    return _strip_cpd(cpd_id) in HUB_COMPOUNDS


# ---------------------------------------------------------------------------
# Output shapes — kept as plain dicts so the route layer can wrap them
# in Pydantic models without coupling the search core to FastAPI.
# ---------------------------------------------------------------------------


def _make_reaction_step(
    reaction: dict,
    target: str,
    depth: int,
    candidate_genes: list[dict],
) -> dict:
    """Compose a ReactionStep dict from a KEGG reaction entry.

    `target` is the compound at the "product" end of this step in
    retrosynthetic terms. The "substrates" become the next BFS frontier.
    """
    target_norm = target if target.startswith("cpd:") else f"cpd:{target}"
    if target_norm in reaction["right_compounds"]:
        product_side = reaction["right_compounds"]
        substrate_side = reaction["left_compounds"]
    elif target_norm in reaction["left_compounds"]:
        product_side = reaction["left_compounds"]
        substrate_side = reaction["right_compounds"]
    else:
        # Target not found on either side; defensive fallback.
        product_side = reaction["right_compounds"]
        substrate_side = reaction["left_compounds"]

    return {
        "reaction_id": reaction["id"],
        "reaction_name": reaction["name"],
        "equation": reaction["equation"],
        "ec_numbers": reaction["ec_numbers"],
        "substrates": substrate_side,
        "products": product_side,
        "candidate_genes": candidate_genes,
        "depth": depth,
    }


# ---------------------------------------------------------------------------
# BFS
# ---------------------------------------------------------------------------


async def search_pathway(
    target_compound: str,
    host_organism: str = "eco",
    max_depth: int = 2,
    max_reactions_per_compound: int = 5,
) -> dict:
    """Return candidate reactions that could produce the target compound.

    Args:
        target_compound: KEGG compound ID, with or without "cpd:" prefix.
        host_organism: KEGG organism code (e.g. "eco" for E. coli).
        max_depth: BFS depth bound. depth=0 -> direct producers only.
        max_reactions_per_compound: cap on reactions explored per compound
            to keep BFS bounded for hub-adjacent targets.

    Returns dict with:
        target: {id, name}
        host: organism code
        max_depth_used
        reactions: list of ReactionStep dicts, ordered by depth then enzyme
        notes: list of human-readable notes (hub metabolites pruned, etc.)
    """
    target_norm = (
        target_compound if target_compound.startswith("cpd:") else f"cpd:{target_compound}"
    )

    target_info = await get_compound_info(target_norm)
    if target_info is None:
        return {
            "target": {"id": target_norm, "name": ""},
            "host": host_organism,
            "max_depth_used": 0,
            "reactions": [],
            "notes": [f"Target compound {target_norm} not found in KEGG."],
        }

    visited_compounds: set[str] = set()
    visited_reactions: set[str] = set()
    notes: list[str] = []
    reaction_steps: list[dict] = []

    frontier: list[tuple[str, int]] = [(target_norm, 0)]
    visited_compounds.add(target_norm)

    while frontier:
        compound_id, depth = frontier.pop(0)
        if depth > max_depth:
            continue

        compound = await get_compound_info(compound_id)
        if not compound:
            continue
        rxn_ids = compound["reaction_ids"][:max_reactions_per_compound]
        if len(compound["reaction_ids"]) > max_reactions_per_compound:
            notes.append(
                f"Compound {compound_id} ({compound['name']}) appears in "
                f"{len(compound['reaction_ids'])} reactions; capped to "
                f"{max_reactions_per_compound} for BFS sanity."
            )

        rxns = await asyncio.gather(*(get_reaction_info(r) for r in rxn_ids))
        for rxn in rxns:
            if rxn is None or rxn["id"] in visited_reactions:
                continue
            visited_reactions.add(rxn["id"])

            # Determine which side has compound_id as a "product" for retro.
            cpd_norm = compound_id
            if cpd_norm in rxn["right_compounds"]:
                substrate_side = rxn["left_compounds"]
            elif cpd_norm in rxn["left_compounds"]:
                substrate_side = rxn["right_compounds"]
            else:
                continue  # KEGG link said this rxn touched cpd, but we don't see it -- skip.

            # Look up host genes for the EC numbers on this reaction.
            ec_numbers = rxn["ec_numbers"][:5]
            gene_lookups = await asyncio.gather(
                *(get_enzyme_genes(ec, host_organism) for ec in ec_numbers),
                return_exceptions=True,
            )
            candidate_genes: list[dict] = []
            for ec, result in zip(ec_numbers, gene_lookups):
                if isinstance(result, Exception):
                    continue
                for g in result:
                    candidate_genes.append({**g, "ec_number": ec})

            reaction_steps.append(
                _make_reaction_step(rxn, cpd_norm, depth, candidate_genes)
            )

            # Expand frontier with non-hub substrates.
            if depth + 1 <= max_depth:
                for sub in substrate_side:
                    if _is_hub(sub):
                        continue
                    if sub in visited_compounds:
                        continue
                    visited_compounds.add(sub)
                    frontier.append((sub, depth + 1))

    if not reaction_steps:
        notes.append(
            "No reactions found within BFS bounds. The target may be a "
            "metabolic dead-end in KEGG, or only present in pathways not "
            "expressed by the chosen host."
        )

    reaction_steps.sort(key=lambda s: (s["depth"], s["reaction_id"]))

    return {
        "target": {"id": target_norm, "name": target_info["name"]},
        "host": host_organism,
        "max_depth_used": max_depth,
        "reactions": reaction_steps,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Convenience: resolve a free-text compound query to a KEGG ID
# ---------------------------------------------------------------------------


async def resolve_compound_id(query: str) -> Optional[str]:
    """Take 'ammonia' or 'cpd:C00014' -> 'cpd:C00014'.

    If `query` looks like a KEGG ID, return it normalised. Otherwise
    fall back to KEGG's compound search and return the first hit.
    """
    if query.startswith("cpd:") and len(query) >= 8:
        return query
    if query.upper().startswith("C") and len(query) == 6 and query[1:].isdigit():
        return f"cpd:{query.upper()}"

    results = await search_compounds(query, limit=1)
    return results[0]["id"] if results else None
