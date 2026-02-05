"""KEGG API client for fetching metabolic pathway and enzyme information."""

import httpx
from typing import Optional
import re


# KEGG REST API base URL
KEGG_BASE_URL = "https://rest.kegg.jp"


async def search_kegg_pathways(query: str, organism: str = "eco", limit: int = 10) -> list[dict]:
    """
    Search KEGG pathways by keyword.

    Args:
        query: Search term (e.g., "glycolysis", "amino acid")
        organism: KEGG organism code (eco=E. coli, sce=S. cerevisiae)
        limit: Maximum results to return

    Returns:
        List of pathway dictionaries
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Search for pathways
            response = await client.get(
                f"{KEGG_BASE_URL}/find/pathway/{query}"
            )
            response.raise_for_status()

            pathways = []
            for line in response.text.strip().split("\n")[:limit]:
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    pathway_id = parts[0].replace("path:", "")
                    name = parts[1]
                    pathways.append({
                        "id": pathway_id,
                        "name": name,
                        "organism": organism,
                        "url": f"https://www.kegg.jp/pathway/{pathway_id}",
                    })

            return pathways

        except Exception as e:
            print(f"KEGG search error: {e}")
            return []


async def get_pathway_info(pathway_id: str) -> Optional[dict]:
    """
    Get detailed information about a KEGG pathway.

    Args:
        pathway_id: KEGG pathway ID (e.g., "eco00010" for E. coli glycolysis)

    Returns:
        Pathway dictionary with details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/get/{pathway_id}")
            response.raise_for_status()

            return parse_kegg_entry(response.text, "pathway")

        except Exception:
            return None


async def get_pathway_genes(pathway_id: str) -> list[dict]:
    """
    Get genes/enzymes involved in a KEGG pathway.

    Args:
        pathway_id: KEGG pathway ID

    Returns:
        List of gene/enzyme dictionaries
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/link/genes/{pathway_id}")
            response.raise_for_status()

            genes = []
            for line in response.text.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    gene_id = parts[1]
                    genes.append({"id": gene_id})

            # Get details for first 20 genes
            for gene in genes[:20]:
                info = await get_gene_info(gene["id"])
                if info:
                    gene.update(info)

            return genes

        except Exception:
            return []


async def get_gene_info(gene_id: str) -> Optional[dict]:
    """
    Get information about a KEGG gene.

    Args:
        gene_id: KEGG gene ID (e.g., "eco:b0001")

    Returns:
        Gene dictionary with name, description, sequence
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/get/{gene_id}")
            response.raise_for_status()

            return parse_kegg_entry(response.text, "gene")

        except Exception:
            return None


async def get_gene_sequence(gene_id: str, seq_type: str = "ntseq") -> Optional[str]:
    """
    Get nucleotide or amino acid sequence for a gene.

    Args:
        gene_id: KEGG gene ID
        seq_type: "ntseq" for nucleotide, "aaseq" for amino acid

    Returns:
        Sequence string
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/get/{gene_id}/{seq_type}")
            response.raise_for_status()

            # Parse FASTA format
            lines = response.text.strip().split("\n")
            sequence = "".join(line for line in lines if not line.startswith(">"))
            return sequence.upper()

        except Exception:
            return None


async def search_enzymes(query: str, limit: int = 10) -> list[dict]:
    """
    Search KEGG enzymes by name or EC number.

    Args:
        query: Search term or EC number (e.g., "kinase", "2.7.1.1")
        limit: Maximum results

    Returns:
        List of enzyme dictionaries
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/find/enzyme/{query}")
            response.raise_for_status()

            enzymes = []
            for line in response.text.strip().split("\n")[:limit]:
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    ec_number = parts[0].replace("ec:", "")
                    name = parts[1]
                    enzymes.append({
                        "ec_number": ec_number,
                        "name": name,
                        "url": f"https://www.kegg.jp/entry/{ec_number}",
                    })

            return enzymes

        except Exception:
            return []


async def get_enzyme_info(ec_number: str) -> Optional[dict]:
    """
    Get detailed information about an enzyme.

    Args:
        ec_number: EC number (e.g., "2.7.1.1")

    Returns:
        Enzyme dictionary with details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{KEGG_BASE_URL}/get/ec:{ec_number}")
            response.raise_for_status()

            return parse_kegg_entry(response.text, "enzyme")

        except Exception:
            return None


def parse_kegg_entry(text: str, entry_type: str) -> dict:
    """Parse KEGG flat file format into dictionary."""
    result = {}
    current_field = None
    current_value = []

    for line in text.split("\n"):
        if not line:
            continue

        # Check if this is a new field
        if line[0] != " ":
            # Save previous field
            if current_field:
                result[current_field.lower()] = "\n".join(current_value).strip()

            # Parse new field
            parts = line.split(None, 1)
            current_field = parts[0]
            current_value = [parts[1]] if len(parts) > 1 else []
        else:
            # Continue previous field
            current_value.append(line.strip())

    # Save last field
    if current_field:
        result[current_field.lower()] = "\n".join(current_value).strip()

    # Extract specific fields based on entry type
    if entry_type == "pathway":
        return {
            "id": result.get("entry", "").split()[0],
            "name": result.get("name", ""),
            "description": result.get("description", ""),
            "class": result.get("class", ""),
        }
    elif entry_type == "gene":
        name = result.get("name", "")
        return {
            "id": result.get("entry", "").split()[0],
            "name": name.split(",")[0].strip() if name else "",
            "definition": result.get("definition", ""),
            "organism": result.get("organism", ""),
        }
    elif entry_type == "enzyme":
        return {
            "ec_number": result.get("entry", "").split()[0].replace("EC ", ""),
            "name": result.get("name", "").split("\n")[0],
            "reaction": result.get("reaction", ""),
            "substrate": result.get("substrate", ""),
            "product": result.get("product", ""),
        }

    return result


# Organism code mappings
ORGANISM_CODES = {
    "ecoli": "eco",
    "e. coli": "eco",
    "escherichia coli": "eco",
    "yeast": "sce",
    "s. cerevisiae": "sce",
    "saccharomyces cerevisiae": "sce",
}


def get_organism_code(organism: str) -> str:
    """Convert organism name to KEGG code."""
    return ORGANISM_CODES.get(organism.lower(), organism[:3])
