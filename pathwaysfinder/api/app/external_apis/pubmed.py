"""PubMed/NCBI E-utilities API client for fetching research papers."""

import httpx
from typing import Optional
import xml.etree.ElementTree as ET


PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


async def search_pubmed(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search PubMed for papers matching the query.

    Args:
        query: Search query (part name, gene name, keywords)
        max_results: Maximum number of results to return

    Returns:
        List of paper dictionaries with title, authors, abstract, doi, pmid, url
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Search for paper IDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }

        search_response = await client.get(PUBMED_SEARCH_URL, params=search_params)
        search_response.raise_for_status()
        search_data = search_response.json()

        id_list = search_data.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return []

        # Step 2: Fetch paper details
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
        }

        fetch_response = await client.get(PUBMED_FETCH_URL, params=fetch_params)
        fetch_response.raise_for_status()

        # Parse XML response
        papers = parse_pubmed_xml(fetch_response.text)

        return papers


def parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed XML response into list of paper dictionaries."""
    papers = []

    try:
        root = ET.fromstring(xml_text)

        for article in root.findall(".//PubmedArticle"):
            paper = {}

            # PMID
            pmid_elem = article.find(".//PMID")
            if pmid_elem is not None:
                paper["pmid"] = pmid_elem.text
                paper["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid_elem.text}/"

            # Title
            title_elem = article.find(".//ArticleTitle")
            if title_elem is not None:
                paper["title"] = "".join(title_elem.itertext())

            # Authors
            authors = []
            for author in article.findall(".//Author"):
                last_name = author.find("LastName")
                fore_name = author.find("ForeName")
                if last_name is not None:
                    name = last_name.text
                    if fore_name is not None:
                        name = f"{fore_name.text} {name}"
                    authors.append(name)
            paper["authors"] = authors

            # Abstract
            abstract_parts = []
            for abstract_text in article.findall(".//AbstractText"):
                label = abstract_text.get("Label", "")
                text = "".join(abstract_text.itertext())
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            paper["abstract"] = " ".join(abstract_parts) if abstract_parts else None

            # Journal
            journal_elem = article.find(".//Journal/Title")
            if journal_elem is not None:
                paper["journal"] = journal_elem.text

            # Year
            year_elem = article.find(".//PubDate/Year")
            if year_elem is not None:
                paper["year"] = year_elem.text

            # DOI
            for article_id in article.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    paper["doi"] = article_id.text
                    paper["doi_url"] = f"https://doi.org/{article_id.text}"
                    break

            papers.append(paper)

    except ET.ParseError:
        pass

    return papers


async def search_papers_for_part(part_name: str, part_type: str, description: Optional[str] = None) -> list[dict]:
    """
    Search for papers related to a genetic part.

    Builds a smart query based on part name and type.
    """
    # Build search queries
    queries = []

    # Direct part name search (for iGEM parts)
    if part_name.startswith("BBa_"):
        queries.append(f'"{part_name}"')

    # Type-specific searches
    type_terms = {
        "promoter": "promoter",
        "rbs": "ribosome binding site",
        "terminator": "terminator",
        "gene": "gene expression",
    }

    if part_type in type_terms:
        # Add synthetic biology context
        queries.append(f'{type_terms[part_type]} AND (synthetic biology OR genetic engineering)')

    # Search with description keywords if available
    if description:
        # Extract key terms from description
        key_terms = []
        if "GFP" in description.upper():
            key_terms.append("GFP green fluorescent protein")
        if "RFP" in description.upper() or "mRFP" in description:
            key_terms.append("RFP red fluorescent protein")
        if "LacI" in description:
            key_terms.append("LacI repressor")
        if "TetR" in description:
            key_terms.append("TetR repressor")
        if "Anderson" in description:
            key_terms.append("Anderson promoter collection")

        for term in key_terms:
            queries.append(term)

    # Execute searches and combine results
    all_papers = []
    seen_pmids = set()

    for query in queries[:3]:  # Limit to 3 queries to avoid rate limiting
        try:
            papers = await search_pubmed(query, max_results=3)
            for paper in papers:
                pmid = paper.get("pmid")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    all_papers.append(paper)
        except Exception:
            continue

    return all_papers[:5]  # Return max 5 papers
