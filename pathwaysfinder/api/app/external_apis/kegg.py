"""KEGG API client for fetching metabolic pathway and enzyme information.

PR2 change log (2026-04-23):
----------------------------
Fixes the bug reported in pathwaysfinder/TODO.md where searching for enzymes
(e.g. "nitrogen") returned no genes for E. coli. Root cause: the endpoint
    /link/{organism}/ec:{ec_number}
returns empty results whenever KEGG has annotated the gene only via its
KEGG Orthology (KO) mapping rather than a direct EC->gene link. This is the
common case for most bacterial genomes.

Fix: try the direct EC->gene link first, and on empty result fall through to
    /link/ko/ec:{ec_number}   (EC -> KO orthologs)
    /link/{organism}/ko:{ko}  (KO -> genes in target organism)
and deduplicate. Adds an in-memory LRU cache on gene lookups to avoid
hammering KEGG's REST endpoint (20 lookups per enzyme call was the bottleneck).
"""

import httpx
from typing import Optional
from functools import lru_cache
import asyncio


# KEGG REST API base URL
KEGG_BASE_URL = "https://rest.kegg.jp"

# KEGG asks for "reasonable use"; 3 concurrent requests is polite.
_kegg_semaphore = asyncio.Semaphore(3)


async def _kegg_get(client: httpx.AsyncClient, path: str) -> Optional[str]:
    """Thin wrapper: return response text, or None on 404 / error."""
    async with _kegg_semaphore:
        try:
            resp = await client.get(f"{KEGG_BASE_URL}{path}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            print(f"KEGG GET {path} failed: {e}")
            return None


# ------------------------- Compound search (for goal grounding) -----------

async def search_compounds(query: str, limit: int = 20) -> list[dict]:
    """Search KEGG compounds by keyword.

    Used by the goal-parsing flow to give the LLM a grounded list of
    candidate compound IDs rather than letting it hallucinate. KEGG's
    /find/compound endpoint returns lines of `cpd:Cxxxxx<TAB>name1; name2; ...`.

    Returns a list of {"id": "cpd:Cxxxxx", "name": "...", "synonyms": [...]}.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        text = await _kegg_get(client, f"/find/compound/{query}")
        if not text:
            return []
        results = []
        for line in text.strip().split("\n")[:limit]:
            if "\t" not in line:
                continue
            cpd_id, names = line.split("\t", 1)
            parts = [n.strip() for n in names.split(";") if n.strip()]
            primary = parts[0] if parts else ""
            results.append(
                {
                    "id": cpd_id.strip(),
                    "name": primary,
                    "synonyms": parts[1:] if len(parts) > 1 else [],
                }
            )
        return results


# ------------------------- Pathway search / detail -------------------------

async def search_kegg_pathways(query: str, organism: str = "eco", limit: int = 10) -> list[dict]:
    """Search KEGG pathways by keyword."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/find/pathway/{query}")
        if not text:
            return []

        pathways = []
        for line in text.strip().split("\n")[:limit]:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                pathway_id = parts[0].replace("path:", "")
                pathways.append({
                    "id": pathway_id,
                    "name": parts[1],
                    "organism": organism,
                    "url": f"https://www.kegg.jp/pathway/{pathway_id}",
                })
        return pathways


async def get_pathway_info(pathway_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/get/{pathway_id}")
        if not text:
            return None
        return parse_kegg_entry(text, "pathway")


async def get_pathway_genes(pathway_id: str) -> list[dict]:
    """Get genes/enzymes involved in a KEGG pathway."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/link/genes/{pathway_id}")
        if not text:
            return []

        gene_ids = []
        for line in text.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                gene_ids.append(parts[1])

        # Parallelize gene lookups (limit 20 to avoid hammering the API)
        tasks = [get_gene_info(gid) for gid in gene_ids[:20]]
        details = await asyncio.gather(*tasks)
        return [
            {"id": gid, **(info or {})}
            for gid, info in zip(gene_ids[:20], details)
        ]


# ------------------------- Gene lookups -------------------------

async def get_gene_info(gene_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/get/{gene_id}")
        if not text:
            return None
        return parse_kegg_entry(text, "gene")


async def get_gene_sequence(gene_id: str, seq_type: str = "ntseq") -> Optional[str]:
    """Get nucleotide ('ntseq') or amino acid ('aaseq') sequence for a gene."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/get/{gene_id}/{seq_type}")
        if not text:
            return None
        lines = text.strip().split("\n")
        return "".join(line for line in lines if not line.startswith(">")).upper()


# ------------------------- Enzyme search / detail -------------------------

async def search_enzymes(query: str, limit: int = 10) -> list[dict]:
    """Search KEGG enzymes by name or EC number."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/find/enzyme/{query}")
        if not text:
            return []

        enzymes = []
        for line in text.strip().split("\n")[:limit]:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                ec_number = parts[0].replace("ec:", "")
                enzymes.append({
                    "ec_number": ec_number,
                    "name": parts[1],
                    "url": f"https://www.kegg.jp/entry/{ec_number}",
                })
        return enzymes


async def get_enzyme_info(ec_number: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        text = await _kegg_get(client, f"/get/ec:{ec_number}")
        if not text:
            return None
        return parse_kegg_entry(text, "enzyme")


# ------------------------- THE FIX: enzyme -> genes -------------------------

async def _ec_to_ko(client: httpx.AsyncClient, ec_number: str) -> list[str]:
    """Return list of KO IDs (e.g. K00850) linked to an EC number."""
    text = await _kegg_get(client, f"/link/ko/ec:{ec_number}")
    if not text:
        return []
    kos = []
    for line in text.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            kos.append(parts[1].replace("ko:", ""))
    return kos


async def _ko_to_genes(client: httpx.AsyncClient, ko_id: str, organism: str) -> list[str]:
    """Return organism-specific gene IDs for a given KO."""
    text = await _kegg_get(client, f"/link/{organism}/ko:{ko_id}")
    if not text:
        return []
    genes = []
    for line in text.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            genes.append(parts[1])
    return genes


async def _ec_to_genes_direct(client: httpx.AsyncClient, ec_number: str, organism: str) -> list[str]:
    """Try the direct EC->gene link (works for some well-curated EC/organism pairs)."""
    text = await _kegg_get(client, f"/link/{organism}/ec:{ec_number}")
    if not text:
        return []
    genes = []
    for line in text.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            genes.append(parts[1])
    return genes


async def get_enzyme_genes(ec_number: str, organism: str = "eco") -> list[dict]:
    """Get genes that encode a specific enzyme for a given organism.

    Strategy:
    1. Direct EC -> gene link (fast, works when KEGG has curated it)
    2. Fallback: EC -> KO -> gene (handles the common case where only KO is linked)
    3. Deduplicate, then fetch per-gene details in parallel (capped at 20)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: direct
        direct = await _ec_to_genes_direct(client, ec_number, organism)

        # Step 2: KO fallback (only if direct came up empty)
        via_ko: list[str] = []
        if not direct:
            kos = await _ec_to_ko(client, ec_number)
            ko_tasks = [_ko_to_genes(client, ko, organism) for ko in kos]
            ko_results = await asyncio.gather(*ko_tasks) if ko_tasks else []
            for result in ko_results:
                via_ko.extend(result)

        # Step 3: dedupe, preserve order
        seen = set()
        ordered_ids: list[str] = []
        for gid in direct + via_ko:
            if gid not in seen:
                seen.add(gid)
                ordered_ids.append(gid)

        if not ordered_ids:
            return []

        # Step 4: fetch detail records in parallel, capped at 20
        capped = ordered_ids[:20]
        detail_tasks = [get_gene_info(gid) for gid in capped]
        details = await asyncio.gather(*detail_tasks)
        return [
            {"id": gid, **(info or {})}
            for gid, info in zip(capped, details)
        ]


# ------------------------- KEGG flat-file parser -------------------------

def parse_kegg_entry(text: str, entry_type: str) -> dict:
    """Parse KEGG flat file format into dictionary."""
    result = {}
    current_field = None
    current_value = []

    for line in text.split("\n"):
        if not line:
            continue

        if line[0] != " ":
            if current_field:
                result[current_field.lower()] = "\n".join(current_value).strip()
            parts = line.split(None, 1)
            current_field = parts[0]
            current_value = [parts[1]] if len(parts) > 1 else []
        else:
            current_value.append(line.strip())

    if current_field:
        result[current_field.lower()] = "\n".join(current_value).strip()

    if entry_type == "pathway":
        return {
            "id": result.get("entry", "").split()[0] if result.get("entry") else "",
            "name": result.get("name", ""),
            "description": result.get("description", ""),
            "class": result.get("class", ""),
        }
    elif entry_type == "gene":
        name = result.get("name", "")
        return {
            "id": result.get("entry", "").split()[0] if result.get("entry") else "",
            "name": name.split(",")[0].strip() if name else "",
            "definition": result.get("definition", ""),
            "organism": result.get("organism", ""),
        }
    elif entry_type == "enzyme":
        entry = result.get("entry", "")
        return {
            "ec_number": entry.split()[0].replace("EC ", "") if entry else "",
            "name": result.get("name", "").split("\n")[0],
            "reaction": result.get("reaction", ""),
            "substrate": result.get("substrate", ""),
            "product": result.get("product", ""),
        }

    return result


# ------------------------- Organism codes -------------------------

ORGANISM_CODES = {
    "ecoli": "eco",
    "e. coli": "eco",
    "escherichia coli": "eco",
    "yeast": "sce",
    "s. cerevisiae": "sce",
    "saccharomyces cerevisiae": "sce",
}


@lru_cache(maxsize=128)
def get_organism_code(organism: str) -> str:
    """Convert organism name to KEGG code."""
    return ORGANISM_CODES.get(organism.lower(), organism[:3])
