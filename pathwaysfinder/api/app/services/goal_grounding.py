"""Pre-LLM grounding: turn a free-text goal into vetted KEGG/UniProt candidates.

The LLM goal parser is constrained to use only IDs from a candidate list.
This module builds that list by extracting probable target keywords from
the user's goal and querying KEGG and UniProt for matching compounds and
proteins.

Keyword extraction is intentionally simple — a small Dutch/English
substance dictionary plus a fall-through to the raw query. We don't need
NLP here; the LLM does the heavy interpretation.
"""

from __future__ import annotations

import asyncio
import logging
import re

from app.external_apis.kegg import search_compounds
from app.external_apis.uniprot import search_proteins

logger = logging.getLogger(__name__)


# Dutch / English substance keywords that should map to KEGG compound search.
# Kept tiny on purpose — for harder cases the LLM can still do without grounding.
_SUBSTANCE_HINTS_NL_EN = {
    "ammoniak": "ammonia",
    "stikstof": "nitrogen",
    "nitraat": "nitrate",
    "nitriet": "nitrite",
    "kerosine": "kerosene",
    "alkaan": "alkane",
    "alkanen": "alkane",
    "kaas": "casein",  # closest meaningful KEGG/UniProt anchor
    "caseïne": "casein",
    "wei": "whey",
    "pfas": "perfluoroalkyl",
    "bloedplasma": "albumin",  # closest searchable anchor
    "albumine": "albumin",
    "immunoglobuline": "immunoglobulin",
    "antilichamen": "immunoglobulin",
    "antilichaam": "immunoglobulin",
    "stollingsfactor": "coagulation factor",
    "waterstof": "hydrogen",
    "fotosynthese": "photosynthesis",
    "ethanol": "ethanol",
    "methanol": "methanol",
}

# Hint words that indicate the target is a protein (search UniProt).
_PROTEIN_HINTS = {
    "eiwit",
    "eiwitten",
    "protein",
    "proteins",
    "enzym",
    "enzyme",
    "casein",
    "caseïne",
    "albumin",
    "albumine",
    "antibody",
    "antilichaam",
    "immunoglobulin",
    "factor",
    "chymosin",
    "rennet",
    "stremsel",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _extract_keywords(query: str) -> tuple[list[str], list[str]]:
    """Return (compound_keywords, protein_keywords).

    Both lists are de-duplicated and limited; the LLM is the heavy lifter,
    we just need to seed candidate IDs from one or two well-chosen searches.
    """
    norm = _normalize(query)
    tokens = re.findall(r"[a-zà-ÿ0-9\-]+", norm)

    compound_kws: list[str] = []
    protein_kws: list[str] = []

    for tok in tokens:
        mapped = _SUBSTANCE_HINTS_NL_EN.get(tok)
        if mapped:
            if mapped in {"casein", "albumin", "immunoglobulin", "coagulation factor"}:
                protein_kws.append(mapped)
            else:
                compound_kws.append(mapped)

    # If the goal mentions "eiwit / protein / enzyme" but no specific protein,
    # fall back to a few generic salient nouns from the query.
    if any(t in _PROTEIN_HINTS for t in tokens) and not protein_kws:
        nouns = [t for t in tokens if len(t) > 4 and t not in _PROTEIN_HINTS]
        protein_kws.extend(nouns[:2])

    # If we found nothing, send the longest non-trivial token to KEGG.
    if not compound_kws and not protein_kws:
        candidates = sorted(
            (t for t in tokens if len(t) > 3 and t.isalpha()), key=len, reverse=True
        )
        if candidates:
            compound_kws.append(candidates[0])

    # Cap to a reasonable number of upstream calls.
    return list(dict.fromkeys(compound_kws))[:3], list(dict.fromkeys(protein_kws))[:3]


async def build_candidates(
    query: str,
    *,
    kegg_limit_per_keyword: int = 8,
    uniprot_limit_per_keyword: int = 6,
) -> tuple[list[dict], list[dict]]:
    """Return (kegg_candidates, uniprot_candidates) for the LLM."""
    compound_kws, protein_kws = _extract_keywords(query)
    logger.info(
        f"Grounding for query={query!r}: "
        f"compound_kws={compound_kws}, protein_kws={protein_kws}"
    )

    kegg_tasks = [search_compounds(kw, limit=kegg_limit_per_keyword) for kw in compound_kws]
    uniprot_tasks = [
        search_proteins(kw, limit=uniprot_limit_per_keyword) for kw in protein_kws
    ]

    kegg_results = await asyncio.gather(*kegg_tasks, return_exceptions=True) if kegg_tasks else []
    uniprot_results = (
        await asyncio.gather(*uniprot_tasks, return_exceptions=True) if uniprot_tasks else []
    )

    seen_kegg: set[str] = set()
    kegg_candidates: list[dict] = []
    for batch in kegg_results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            if item["id"] in seen_kegg:
                continue
            seen_kegg.add(item["id"])
            kegg_candidates.append(item)

    seen_uniprot: set[str] = set()
    uniprot_candidates: list[dict] = []
    for batch in uniprot_results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            acc = item.get("accession")
            if not acc or acc in seen_uniprot:
                continue
            seen_uniprot.add(acc)
            uniprot_candidates.append(
                {
                    "accession": acc,
                    "name": item.get("name") or item.get("protein_name") or "",
                    "organism": item.get("organism") or "",
                }
            )

    return kegg_candidates[:25], uniprot_candidates[:25]
