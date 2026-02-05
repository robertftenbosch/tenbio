"""UniProt API client for fetching protein information."""

import httpx
from typing import Optional


# UniProt REST API
UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"


async def search_proteins(
    query: str,
    organism: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search UniProt for proteins.

    Args:
        query: Search term (protein name, gene name, function)
        organism: Filter by organism (e.g., "Escherichia coli", "Saccharomyces cerevisiae")
        limit: Maximum results

    Returns:
        List of protein dictionaries
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Build search query
            search_query = query
            if organism:
                org_map = {
                    "ecoli": "Escherichia coli",
                    "yeast": "Saccharomyces cerevisiae",
                }
                org_name = org_map.get(organism.lower(), organism)
                search_query = f"{query} AND organism_name:{org_name}"

            params = {
                "query": search_query,
                "format": "json",
                "size": limit,
                "fields": "accession,id,protein_name,gene_names,organism_name,length,sequence",
            }

            response = await client.get(f"{UNIPROT_BASE_URL}/search", params=params)
            response.raise_for_status()

            data = response.json()
            proteins = []

            for result in data.get("results", []):
                protein = parse_uniprot_result(result)
                if protein:
                    proteins.append(protein)

            return proteins

        except Exception as e:
            print(f"UniProt search error: {e}")
            return []


async def get_protein_by_accession(accession: str) -> Optional[dict]:
    """
    Get protein details by UniProt accession.

    Args:
        accession: UniProt accession (e.g., "P00761", "P0A6F5")

    Returns:
        Protein dictionary with full details
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {
                "format": "json",
                "fields": "accession,id,protein_name,gene_names,organism_name,length,sequence,cc_function,cc_catalytic_activity,ft_domain,xref_pdb",
            }

            response = await client.get(f"{UNIPROT_BASE_URL}/{accession}", params=params)
            response.raise_for_status()

            data = response.json()
            return parse_uniprot_result(data, full=True)

        except Exception:
            return None


async def get_protein_sequence(accession: str) -> Optional[str]:
    """
    Get protein amino acid sequence.

    Args:
        accession: UniProt accession

    Returns:
        Amino acid sequence string
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{UNIPROT_BASE_URL}/{accession}.fasta")
            response.raise_for_status()

            # Parse FASTA
            lines = response.text.strip().split("\n")
            sequence = "".join(line for line in lines if not line.startswith(">"))
            return sequence

        except Exception:
            return None


async def search_enzymes_by_ec(ec_number: str, organism: str | None = None, limit: int = 10) -> list[dict]:
    """
    Search for proteins with a specific EC number.

    Args:
        ec_number: EC number (e.g., "2.7.1.1")
        organism: Filter by organism
        limit: Maximum results

    Returns:
        List of protein dictionaries
    """
    query = f"ec:{ec_number}"
    return await search_proteins(query, organism=organism, limit=limit)


def parse_uniprot_result(data: dict, full: bool = False) -> Optional[dict]:
    """Parse UniProt JSON result into simplified dictionary."""
    try:
        # Basic info
        accession = data.get("primaryAccession", "")
        entry_name = data.get("uniProtkbId", "")

        # Protein name
        protein_name = ""
        protein_desc = data.get("proteinDescription", {})
        if "recommendedName" in protein_desc:
            protein_name = protein_desc["recommendedName"].get("fullName", {}).get("value", "")
        elif "submissionNames" in protein_desc:
            names = protein_desc["submissionNames"]
            if names:
                protein_name = names[0].get("fullName", {}).get("value", "")

        # Gene names
        gene_names = []
        for gene in data.get("genes", []):
            if "geneName" in gene:
                gene_names.append(gene["geneName"].get("value", ""))

        # Organism
        organism = ""
        org_data = data.get("organism", {})
        if "scientificName" in org_data:
            organism = org_data["scientificName"]

        # Length and sequence
        sequence_data = data.get("sequence", {})
        length = sequence_data.get("length", 0)
        sequence = sequence_data.get("value", "")

        result = {
            "accession": accession,
            "entry_name": entry_name,
            "protein_name": protein_name,
            "gene_names": gene_names,
            "organism": organism,
            "length": length,
            "sequence": sequence,
            "url": f"https://www.uniprot.org/uniprotkb/{accession}",
        }

        if full:
            # Add function annotation
            comments = data.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        result["function"] = texts[0].get("value", "")

                if comment.get("commentType") == "CATALYTIC ACTIVITY":
                    reactions = comment.get("reaction", {})
                    result["catalytic_activity"] = reactions.get("name", "")

            # Add PDB structures
            xrefs = data.get("uniProtKBCrossReferences", [])
            pdb_ids = [
                xref.get("id") for xref in xrefs
                if xref.get("database") == "PDB"
            ]
            result["pdb_ids"] = pdb_ids[:5]  # Limit to 5

        return result

    except Exception:
        return None


async def get_protein_features(accession: str) -> list[dict]:
    """
    Get protein features (domains, active sites, etc.)

    Args:
        accession: UniProt accession

    Returns:
        List of feature dictionaries
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            params = {
                "format": "json",
                "fields": "ft_domain,ft_region,ft_site,ft_act_site,ft_binding",
            }

            response = await client.get(f"{UNIPROT_BASE_URL}/{accession}", params=params)
            response.raise_for_status()

            data = response.json()
            features = []

            for feature in data.get("features", []):
                features.append({
                    "type": feature.get("type", ""),
                    "description": feature.get("description", ""),
                    "start": feature.get("location", {}).get("start", {}).get("value"),
                    "end": feature.get("location", {}).get("end", {}).get("value"),
                })

            return features

        except Exception:
            return []
