"""iGEM Registry API client for fetching BioBrick parts."""

import httpx
import xml.etree.ElementTree as ET
from typing import Optional
import re


# iGEM Registry URLs (use HTTPS and follow redirects)
IGEM_PART_URL = "https://parts.igem.org/cgi/xml/part.cgi"
IGEM_SEARCH_URL = "https://parts.igem.org/cgi/xml/partslist.cgi"
IGEM_PART_PAGE_URL = "https://parts.igem.org/Part:"

# Headers to mimic browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def fetch_igem_part(part_name: str) -> Optional[dict]:
    """
    Fetch a single part from the iGEM Registry.

    Args:
        part_name: The part name (e.g., "BBa_J23100")

    Returns:
        Part dictionary or None if not found
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=HEADERS) as client:
        # First try the XML API
        try:
            response = await client.get(
                IGEM_PART_URL,
                params={"part": part_name}
            )
            if response.status_code == 200 and "<?xml" in response.text:
                return parse_igem_part_xml(response.text)
        except Exception:
            pass

        # Fallback: scrape the part page
        try:
            response = await client.get(f"{IGEM_PART_PAGE_URL}{part_name}")
            if response.status_code == 200:
                return parse_igem_part_page(response.text, part_name)
        except Exception:
            pass

        return None


async def search_igem_parts(
    part_type: Optional[str] = None,
    search_term: Optional[str] = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Search for parts in the iGEM Registry.

    Args:
        part_type: Filter by part type (e.g., "Regulatory", "Coding", "Reporter")
        search_term: Search in part names and descriptions
        max_results: Maximum number of results

    Returns:
        List of part dictionaries
    """
    # Map our types to iGEM categories
    type_mapping = {
        "promoter": "Regulatory",
        "rbs": "Regulatory",
        "terminator": "Terminator",
        "gene": "Coding",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            params = {}
            if part_type and part_type in type_mapping:
                params["type"] = type_mapping[part_type]

            response = await client.get(IGEM_SEARCH_URL, params=params)
            response.raise_for_status()

            parts = parse_igem_parts_list_xml(response.text, max_results)

            # Filter by search term if provided
            if search_term:
                search_lower = search_term.lower()
                parts = [
                    p for p in parts
                    if search_lower in p.get("name", "").lower()
                    or search_lower in (p.get("description") or "").lower()
                ]

            return parts[:max_results]
        except Exception as e:
            print(f"Error searching iGEM: {e}")
            return []


def parse_igem_part_page(html_text: str, part_name: str) -> Optional[dict]:
    """Parse iGEM part page HTML to extract part info."""
    try:
        part = {
            "name": part_name,
            "source": "iGEM",
        }

        # Extract sequence from the page
        # Look for sequence in various formats
        seq_match = re.search(r'class="seq"[^>]*>([ATGC\s]+)<', html_text, re.IGNORECASE)
        if seq_match:
            part["sequence"] = seq_match.group(1).upper().replace(" ", "").replace("\n", "")

        # Try to find sequence in pre tags
        if not part.get("sequence"):
            seq_match = re.search(r'<pre[^>]*>([ATGC\s]+)</pre>', html_text, re.IGNORECASE)
            if seq_match:
                part["sequence"] = seq_match.group(1).upper().replace(" ", "").replace("\n", "")

        # Extract description
        desc_match = re.search(r'<meta name="description" content="([^"]+)"', html_text)
        if desc_match:
            part["description"] = desc_match.group(1)

        # Determine type from part name or page content
        html_lower = html_text.lower()
        if "promoter" in html_lower:
            part["type"] = "promoter"
        elif "rbs" in html_lower or "ribosome" in html_lower:
            part["type"] = "rbs"
        elif "terminator" in html_lower:
            part["type"] = "terminator"
        else:
            part["type"] = "gene"

        # Only return if we have a sequence
        if part.get("sequence") and len(part["sequence"]) > 10:
            return part

        return None

    except Exception:
        return None


def parse_igem_part_xml(xml_text: str) -> Optional[dict]:
    """Parse iGEM part XML response."""
    try:
        root = ET.fromstring(xml_text)
        part_elem = root.find(".//part")

        if part_elem is None:
            return None

        part = {
            "name": part_elem.findtext("part_name"),
            "description": part_elem.findtext("part_short_desc"),
            "sequence": part_elem.findtext("seq_data", "").upper().replace(" ", "").replace("\n", ""),
            "source": "iGEM",
        }

        # Determine type from part type or categories
        part_type = part_elem.findtext("part_type", "").lower()
        categories = part_elem.findtext("categories", "").lower()

        if "promoter" in part_type or "promoter" in categories:
            part["type"] = "promoter"
        elif "rbs" in part_type or "ribosome" in categories:
            part["type"] = "rbs"
        elif "terminator" in part_type or "terminator" in categories:
            part["type"] = "terminator"
        elif "coding" in part_type or "reporter" in categories or "gene" in categories:
            part["type"] = "gene"
        else:
            part["type"] = "gene"  # Default to gene

        # Try to determine organism
        desc_lower = (part.get("description") or "").lower()
        if "coli" in desc_lower or "e. coli" in desc_lower:
            part["organism"] = "ecoli"
        elif "yeast" in desc_lower or "cerevisiae" in desc_lower:
            part["organism"] = "yeast"

        # Only return if we have a valid sequence
        if part.get("sequence") and len(part["sequence"]) > 0:
            return part

        return None

    except ET.ParseError:
        return None


def parse_igem_parts_list_xml(xml_text: str, max_results: int = 20) -> list[dict]:
    """Parse iGEM parts list XML response."""
    parts = []

    try:
        root = ET.fromstring(xml_text)

        for part_elem in root.findall(".//part")[:max_results * 2]:  # Get extra in case some are filtered
            part = {
                "name": part_elem.findtext("part_name"),
                "description": part_elem.findtext("part_short_desc"),
                "source": "iGEM",
            }

            # Get sequence if available
            seq = part_elem.findtext("seq_data", "")
            if seq:
                part["sequence"] = seq.upper().replace(" ", "").replace("\n", "")

            # Determine type
            part_type = part_elem.findtext("part_type", "").lower()
            if "promoter" in part_type:
                part["type"] = "promoter"
            elif "rbs" in part_type:
                part["type"] = "rbs"
            elif "terminator" in part_type:
                part["type"] = "terminator"
            else:
                part["type"] = "gene"

            # Only include parts with sequences
            if part.get("name") and part.get("sequence"):
                parts.append(part)

            if len(parts) >= max_results:
                break

    except ET.ParseError:
        pass

    return parts


async def fetch_popular_parts(category: Optional[str] = None, limit: int = 10) -> list[dict]:
    """
    Fetch popular/commonly used parts from iGEM Registry.

    Returns hand-curated lists of widely-used parts with known sequences.
    Since the iGEM API is often rate-limited, we use local cached data.
    """
    # Local cache of popular parts with their sequences
    popular_parts_data = {
        "promoter": [
            {"name": "BBa_J23100", "type": "promoter", "description": "Constitutive promoter from Anderson collection. Reference strength: 1.0", "sequence": "TTGACGGCTAGCTCAGTCCTAGGTACAGTGCTAGC", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_J23101", "type": "promoter", "description": "Constitutive promoter from Anderson collection. Relative strength: 0.70", "sequence": "TTTACAGCTAGCTCAGTCCTAGGTATTATGCTAGC", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_J23102", "type": "promoter", "description": "Constitutive promoter from Anderson collection. Relative strength: 0.86", "sequence": "TTGACAGCTAGCTCAGTCCTAGGTACTGTGCTAGC", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_J23119", "type": "promoter", "description": "Strongest constitutive promoter. Relative strength: 2.55", "sequence": "TTGACAGCTAGCTCAGTCCTAGGTATAATGCTAGC", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_R0010", "type": "promoter", "description": "LacI-regulated promoter. Inducible with IPTG.", "sequence": "CAATACGCAAACCGCCTCTCCCCGCGCGTTGGCCGATTCATTAATGCAGCTGGCACGACAGGTTTCCCGACTGGAAAGCGGGCAGTGAGCGCAACGCAATTAATGTGAGTTAGCTCACTCATTAGGCACCCCAGGCTTTACACTTTATGCTTCCGGCTCGTATGTTGTGTGGAATTGTGAGCGGATAACAATTTCACACA", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_R0040", "type": "promoter", "description": "TetR-regulated promoter. Inducible with aTc.", "sequence": "TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC", "organism": "ecoli", "source": "iGEM"},
        ],
        "rbs": [
            {"name": "BBa_B0030", "type": "rbs", "description": "Strong RBS based on Elowitz repressilator.", "sequence": "ATTAAAGAGGAGAAA", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_B0031", "type": "rbs", "description": "Weak RBS. Low translation efficiency.", "sequence": "TCACACAGGAAAG", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_B0032", "type": "rbs", "description": "Medium RBS. Moderate translation efficiency.", "sequence": "TCACACAGGAAAGTACTAG", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_B0034", "type": "rbs", "description": "Very strong RBS. Highest efficiency.", "sequence": "AAAGAGGAGAAA", "organism": "ecoli", "source": "iGEM"},
        ],
        "terminator": [
            {"name": "BBa_B0010", "type": "terminator", "description": "T1 from E. coli rrnB. Strong bidirectional terminator.", "sequence": "CCAGGCATCAAATAAAACGAAAGGCTCAGTCGAAAGACTGGGCCTTTCGTTTTATCTGTTGTTTGTCGGTGAACGCTCTC", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_B0012", "type": "terminator", "description": "TE from E. coli rrnB. Strong forward terminator.", "sequence": "TCACACTGGCTCACCTTCGGGTGGGCCTTTCTGCGTTTATA", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_B0015", "type": "terminator", "description": "Double terminator (B0010+B0012). Very strong.", "sequence": "CCAGGCATCAAATAAAACGAAAGGCTCAGTCGAAAGACTGGGCCTTTCGTTTTATCTGTTGTTTGTCGGTGAACGCTCTCTACTAGAGTCACACTGGCTCACCTTCGGGTGGGCCTTTCTGCGTTTATA", "organism": "ecoli", "source": "iGEM"},
        ],
        "gene": [
            {"name": "BBa_E0040", "type": "gene", "description": "GFPmut3b green fluorescent protein.", "sequence": "ATGCGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTTAAATTTATTTGCACTACTGGAAAACTACCTGTTCCATGGCCAACACTTGTCACTACTTTCGGTTATGGTGTTCAATGCTTTGCGAGATACCCAGATCATATGAAACAGCATGACTTTTTCAAGAGTGCCATGCCCGAAGGTTATGTACAGGAAAGAACTATATTTTTCAAAGATGACGGGAACTACAAGACACGTGCTGAAGTCAAGTTTGAAGGTGATACCCTTGTTAATAGAATCGAGTTAAAAGGTATTGATTTTAAAGAAGATGGAAACATTCTTGGACACAAATTGGAATACAACTATAACTCACACAATGTATACATCATGGCAGACAAACAAAAGAATGGAATCAAAGTTAACTTCAAAATTAGACACAACATTGAAGATGGAAGCGTTCAACTAGCAGACCATTATCAACAAAATACTCCAATTGGCGATGGCCCTGTCCTTTTACCAGACAACCATTACCTGTCCACACAATCTGCCCTTTCGAAAGATCCCAACGAAAAGAGAGACCACATGGTCCTTCTTGAGTTTGTAACAGCTGCTGGGATTACACATGGCATGGATGAACTATACAAATAATAA", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_E1010", "type": "gene", "description": "mRFP1 red fluorescent protein.", "sequence": "ATGGCTTCCTCCGAAGACGTTATCAAAGAGTTCATGCGTTTCAAAGTTCGTATGGAAGGTTCCGTTAACGGTCACGAGTTCGAAATCGAAGGTGAAGGTGAAGGTCGTCCGTACGAAGGTACCCAGACCGCTAAACTGAAAGTTACCAAAGGTGGTCCGCTGCCGTTCGCTTGGGACATCCTGTCCCCGCAGTTCCAGTACGGTTCCAAAGCTTACGTTAAACACCCGGCTGACATCCCGGACTACCTGAAACTGTCCTTCCCGGAAGGTTTCAAATGGGAACGTGTTATGAACTTCGAAGACGGTGGTGTTGTTACCGTTACCCAGGACTCCTCCCTGCAAGACGGTGAGTTCATCTACAAAGTTAAACTGCGTGGTACCAACTTCCCGTCCGACGGTCCGGTTATGCAGAAAAAAACCATGGGTTGGGAAGCTTCCACCGAACGTATGTACCCGGAAGACGGTGCTCTGAAAGGTGAAATCAAAATGCGTCTGAAACTGAAAGACGGTGGTCACTACGACGCTGAAGTTAAAACCACCTACATGGCTAAAAAACCGGTTCAGCTGCCGGGTGCTTACAAAACCGACATCAAACTGGACATCACCTCCCACAACGAAGACTACACCATCGTTGAACAGTACGAACGTGCTGAAGGTCGTCACTCCACCGGTGCTTAATAA", "organism": "ecoli", "source": "iGEM"},
            {"name": "BBa_E0020", "type": "gene", "description": "eCFP cyan fluorescent protein.", "sequence": "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGGGGTGGTGCCCATCCTGGTCGAGCTGGACGGCGACGTAAACGGCCACAAGTTCAGCGTGTCCGGCGAGGGCGAGGGCGATGCCACCTACGGCAAGCTGACCCTGAAGTTCATCTGCACCACCGGCAAGCTGCCCGTGCCCTGGCCCACCCTCGTGACCACCCTGACCTGGGGCGTGCAGTGCTTCAGCCGCTACCCCGACCACATGAAGCAGCACGACTTCTTCAAGTCCGCCATGCCCGAAGGCTACGTCCAGGAGCGCACCATCTTCTTCAAGGACGACGGCAACTACAAGACCCGCGCCGAGGTGAAGTTCGAGGGCGACACCCTGGTGAACCGCATCGAGCTGAAGGGCATCGACTTCAAGGAGGACGGCAACATCCTGGGGCACAAGCTGGAGTACAACTACATCAGCCACAACGTCTATATCACCGCCGACAAGCAGAAGAACGGCATCAAGGCCAACTTCAAGATCCGCCACAACATCGAGGACGGCAGCGTGCAGCTCGCCGACCACTACCAGCAGAACACCCCCATCGGCGACGGCCCCGTGCTGCTGCCCGACAACCACTACCTGAGCACCCAGTCCGCCCTGAGCAAAGACCCCAACGAGAAGCGCGATCACATGGTCCTGCTGGAGTTCGTGACCGCCGCCGGGATCACTCTCGGCATGGACGAGCTGTACAAGTAA", "organism": "ecoli", "source": "iGEM"},
        ],
    }

    parts = []
    if category and category in popular_parts_data:
        parts = popular_parts_data[category][:limit]
    else:
        # Get a mix of all types
        for cat_parts in popular_parts_data.values():
            parts.extend(cat_parts[:3])
        parts = parts[:limit]

    return parts
