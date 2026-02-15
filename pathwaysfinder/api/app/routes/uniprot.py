"""UniProt API routes for protein information."""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.external_apis.uniprot import (
    search_proteins,
    get_protein_by_accession,
    get_protein_sequence,
    search_enzymes_by_ec,
    get_protein_features,
)


router = APIRouter(prefix="/api/v1/uniprot", tags=["UniProt Proteins"])


class ProteinResponse(BaseModel):
    accession: str
    entry_name: str | None = None
    protein_name: str | None = None
    gene_names: list[str] = []
    organism: str | None = None
    length: int | None = None
    sequence: str | None = None
    function: str | None = None
    catalytic_activity: str | None = None
    pdb_ids: list[str] = []
    url: str | None = None


class ProteinListResponse(BaseModel):
    proteins: list[ProteinResponse]
    total: int


class ProteinFeatureResponse(BaseModel):
    type: str
    description: str | None = None
    start: int | None = None
    end: int | None = None


@router.get("/search", response_model=ProteinListResponse)
async def search_uniprot(
    q: str = Query(..., description="Search term (protein name, gene name, function)"),
    organism: str = Query(None, description="Filter by organism: ecoli, yeast, or full name"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search UniProt for proteins.

    Examples:
    - /uniprot/search?q=GFP
    - /uniprot/search?q=kinase&organism=ecoli
    - /uniprot/search?q=DNA polymerase&organism=yeast
    """
    proteins = await search_proteins(q, organism=organism, limit=limit)
    return ProteinListResponse(
        proteins=[ProteinResponse(**p) for p in proteins],
        total=len(proteins)
    )


@router.get("/protein/{accession}", response_model=ProteinResponse)
async def get_protein(
    accession: str,
    include_sequence: bool = Query(True, description="Include amino acid sequence"),
):
    """
    Get detailed protein information by UniProt accession.

    Examples:
    - P00761: Trypsin (Bovine)
    - P0A6F5: GroEL chaperonin (E. coli)
    - P42212: GFP (Aequorea victoria)
    """
    protein = await get_protein_by_accession(accession)
    if not protein:
        raise HTTPException(status_code=404, detail=f"Protein {accession} not found")

    if not include_sequence:
        protein["sequence"] = None

    return ProteinResponse(**protein)


@router.get("/protein/{accession}/sequence")
async def get_sequence(accession: str):
    """
    Get protein amino acid sequence in FASTA format.
    """
    sequence = await get_protein_sequence(accession)
    if not sequence:
        raise HTTPException(status_code=404, detail=f"Sequence not found for {accession}")

    return {
        "accession": accession,
        "sequence": sequence,
        "length": len(sequence),
    }


@router.get("/protein/{accession}/features", response_model=list[ProteinFeatureResponse])
async def get_features(accession: str):
    """
    Get protein features (domains, active sites, binding sites).
    """
    features = await get_protein_features(accession)
    return [ProteinFeatureResponse(**f) for f in features]


@router.get("/enzymes/ec/{ec_number}", response_model=ProteinListResponse)
async def search_by_ec(
    ec_number: str,
    organism: str = Query(None, description="Filter by organism"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search for proteins with a specific EC number.

    Examples:
    - /uniprot/enzymes/ec/2.7.1.1 (hexokinases)
    - /uniprot/enzymes/ec/1.1.1.1 (alcohol dehydrogenases)
    """
    proteins = await search_enzymes_by_ec(ec_number, organism=organism, limit=limit)
    return ProteinListResponse(
        proteins=[ProteinResponse(**p) for p in proteins],
        total=len(proteins)
    )


# Common protein lookups for synthetic biology
COMMON_PROTEINS = {
    "gfp": "P42212",  # Green fluorescent protein
    "rfp": "Q9U6Y8",  # DsRed (RFP)
    "mcherry": "X5DSL3",  # mCherry
    "laci": "P03023",  # Lac repressor
    "tetr": "P04483",  # Tet repressor
    "cas9": "Q99ZW2",  # Cas9 from S. pyogenes
}


@router.get("/common/{protein_name}", response_model=ProteinResponse)
async def get_common_protein(protein_name: str):
    """
    Get information about commonly used proteins in synthetic biology.

    Available: gfp, rfp, mcherry, laci, tetr, cas9
    """
    protein_lower = protein_name.lower()
    if protein_lower not in COMMON_PROTEINS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown common protein: {protein_name}. Available: {', '.join(COMMON_PROTEINS.keys())}"
        )

    accession = COMMON_PROTEINS[protein_lower]
    protein = await get_protein_by_accession(accession)
    if not protein:
        raise HTTPException(status_code=404, detail=f"Could not fetch {protein_name}")

    return ProteinResponse(**protein)
