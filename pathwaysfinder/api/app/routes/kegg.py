"""KEGG API routes for metabolic pathway information."""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.external_apis.kegg import (
    search_kegg_pathways,
    get_pathway_info,
    get_pathway_genes,
    search_enzymes,
    get_enzyme_info,
    get_enzyme_genes,
    get_gene_info,
    get_gene_sequence,
    get_organism_code,
)


router = APIRouter(prefix="/api/v1/kegg", tags=["KEGG Pathways"])


class PathwayResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    organism: str | None = None
    url: str | None = None
    class_: str | None = None

    class Config:
        populate_by_name = True


class PathwayListResponse(BaseModel):
    pathways: list[PathwayResponse]
    total: int


class GeneResponse(BaseModel):
    id: str
    name: str | None = None
    definition: str | None = None
    organism: str | None = None
    sequence: str | None = None


class EnzymeResponse(BaseModel):
    ec_number: str
    name: str | None = None
    reaction: str | None = None
    substrate: str | None = None
    product: str | None = None
    url: str | None = None


class EnzymeListResponse(BaseModel):
    enzymes: list[EnzymeResponse]
    total: int


@router.get("/pathways/search", response_model=PathwayListResponse)
async def search_pathways(
    q: str = Query(..., description="Search term (e.g., 'glycolysis', 'amino acid biosynthesis')"),
    organism: str = Query("ecoli", description="Organism: ecoli, yeast"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search KEGG pathways by keyword.

    Returns metabolic pathways matching the search term.
    """
    org_code = get_organism_code(organism)
    pathways = await search_kegg_pathways(q, organism=org_code, limit=limit)
    return PathwayListResponse(
        pathways=[PathwayResponse(**p) for p in pathways],
        total=len(pathways)
    )


@router.get("/pathways/{pathway_id}", response_model=PathwayResponse)
async def get_pathway(pathway_id: str):
    """
    Get detailed information about a specific KEGG pathway.

    Example pathway IDs:
    - eco00010: Glycolysis / Gluconeogenesis (E. coli)
    - eco00020: Citrate cycle (TCA cycle) (E. coli)
    - sce00010: Glycolysis / Gluconeogenesis (Yeast)
    """
    info = await get_pathway_info(pathway_id)
    if not info:
        return PathwayResponse(
            id=pathway_id,
            name="Unknown pathway",
            url=f"https://www.kegg.jp/pathway/{pathway_id}"
        )
    return PathwayResponse(
        id=info.get("id", pathway_id),
        name=info.get("name", ""),
        description=info.get("description"),
        class_=info.get("class"),
        url=f"https://www.kegg.jp/pathway/{pathway_id}"
    )


@router.get("/pathways/{pathway_id}/genes", response_model=list[GeneResponse])
async def get_genes_in_pathway(
    pathway_id: str,
    include_sequence: bool = Query(False, description="Include nucleotide sequences (slower)"),
):
    """
    Get genes involved in a KEGG pathway.

    Returns enzymes and genes that participate in the pathway.
    """
    genes = await get_pathway_genes(pathway_id)

    results = []
    for gene in genes[:20]:  # Limit to 20 genes
        gene_data = GeneResponse(
            id=gene.get("id", ""),
            name=gene.get("name"),
            definition=gene.get("definition"),
            organism=gene.get("organism"),
        )

        if include_sequence:
            seq = await get_gene_sequence(gene.get("id", ""))
            gene_data.sequence = seq

        results.append(gene_data)

    return results


@router.get("/enzymes/search", response_model=EnzymeListResponse)
async def search_enzymes_route(
    q: str = Query(..., description="Search term or EC number (e.g., 'kinase', '2.7.1.1')"),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Search KEGG enzymes by name or EC number.

    Returns enzyme entries with reaction information.
    """
    enzymes = await search_enzymes(q, limit=limit)
    return EnzymeListResponse(
        enzymes=[EnzymeResponse(**e) for e in enzymes],
        total=len(enzymes)
    )


@router.get("/enzymes/{ec_number}", response_model=EnzymeResponse)
async def get_enzyme(ec_number: str):
    """
    Get detailed information about an enzyme by EC number.

    Example: 2.7.1.1 (hexokinase)
    """
    info = await get_enzyme_info(ec_number)
    if not info:
        return EnzymeResponse(
            ec_number=ec_number,
            url=f"https://www.kegg.jp/entry/ec:{ec_number}"
        )
    return EnzymeResponse(
        ec_number=info.get("ec_number", ec_number),
        name=info.get("name"),
        reaction=info.get("reaction"),
        substrate=info.get("substrate"),
        product=info.get("product"),
        url=f"https://www.kegg.jp/entry/ec:{ec_number}"
    )


@router.get("/enzymes/{ec_number}/genes", response_model=list[GeneResponse])
async def get_genes_for_enzyme(
    ec_number: str,
    organism: str = Query("ecoli", description="Organism: ecoli, yeast"),
    include_sequence: bool = Query(False, description="Include nucleotide sequences (slower)"),
):
    """
    Get genes that encode a specific enzyme for a given organism.

    Example: 1.7.1.4 (nitrate reductase) for E. coli
    """
    org_code = get_organism_code(organism)
    genes = await get_enzyme_genes(ec_number, organism=org_code)

    results = []
    for gene in genes[:20]:  # Limit to 20 genes
        gene_data = GeneResponse(
            id=gene.get("id", ""),
            name=gene.get("name"),
            definition=gene.get("definition"),
            organism=gene.get("organism"),
        )

        if include_sequence:
            seq = await get_gene_sequence(gene.get("id", ""))
            gene_data.sequence = seq

        results.append(gene_data)

    return results


@router.get("/genes/{gene_id}", response_model=GeneResponse)
async def get_gene(
    gene_id: str,
    include_sequence: bool = Query(False, description="Include nucleotide sequence"),
):
    """
    Get information about a specific KEGG gene.

    Example: eco:b0001 (thrL gene in E. coli)
    """
    info = await get_gene_info(gene_id)
    if not info:
        return GeneResponse(id=gene_id)

    result = GeneResponse(
        id=info.get("id", gene_id),
        name=info.get("name"),
        definition=info.get("definition"),
        organism=info.get("organism"),
    )

    if include_sequence:
        result.sequence = await get_gene_sequence(gene_id)

    return result
