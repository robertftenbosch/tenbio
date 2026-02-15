"""SBOL3 export service for pathway designs."""

from typing import Literal

import sbol3

# Sequence Ontology terms
SO_ENGINEERED_REGION = "http://identifiers.org/SO:0000804"
SO_PROMOTER = "http://identifiers.org/SO:0000167"
SO_RBS = "http://identifiers.org/SO:0000139"
SO_CDS = "http://identifiers.org/SO:0000316"
SO_TERMINATOR = "http://identifiers.org/SO:0000141"

# Part type to SO role mapping
PART_TYPE_ROLES = {
    "promoter": SO_PROMOTER,
    "rbs": SO_RBS,
    "gene": SO_CDS,
    "terminator": SO_TERMINATOR,
}

NAMESPACE = "https://pathwaysfinder.app/designs/"


def export_pathway_sbol3(
    name: str,
    description: str,
    parts: list[dict],
    file_format: Literal["json-ld", "rdf-xml"] = "json-ld",
) -> str:
    """
    Export a pathway design as an SBOL3 document.

    Args:
        name: Pathway name (used as display_id)
        description: Pathway description
        parts: List of dicts with keys: name, type, sequence, description
        file_format: Output format ("json-ld" or "rdf-xml")

    Returns:
        SBOL3 document as string
    """
    sbol3.set_namespace(NAMESPACE)
    doc = sbol3.Document()

    # Sanitize name for use as SBOL display_id
    pathway_id = _sanitize_display_id(name)

    # Create top-level Component for the pathway
    pathway = sbol3.Component(
        pathway_id,
        sbol3.SBO_DNA,
        roles=[SO_ENGINEERED_REGION],
        description=description,
        name=name,
    )
    doc.add(pathway)

    sub_components = []

    for idx, part in enumerate(parts):
        part_id = _sanitize_display_id(f"{part['name']}_{idx}")
        role = PART_TYPE_ROLES.get(part["type"], SO_CDS)

        # Create Sequence for this part
        seq = sbol3.Sequence(
            f"{part_id}_seq",
            elements=part.get("sequence", ""),
            encoding=sbol3.IUPAC_DNA_ENCODING,
        )
        doc.add(seq)

        # Create Component for this part
        component = sbol3.Component(
            part_id,
            sbol3.SBO_DNA,
            roles=[role],
            sequences=[seq],
            description=part.get("description", ""),
            name=part["name"],
        )
        doc.add(component)

        # Add as SubComponent of the pathway
        sub = sbol3.SubComponent(component)
        pathway.features.append(sub)
        sub_components.append(sub)

    # Add SBOL_MEETS constraints for sequential ordering
    for i in range(len(sub_components) - 1):
        constraint = sbol3.Constraint(
            sbol3.SBOL_MEETS,
            sub_components[i],
            sub_components[i + 1],
        )
        pathway.constraints.append(constraint)

    # Serialize
    if file_format == "rdf-xml":
        return doc.write_string(sbol3.RDF_XML)
    else:
        return doc.write_string(sbol3.JSONLD)


def _sanitize_display_id(name: str) -> str:
    """Sanitize a name for use as an SBOL display_id (alphanumeric + underscore)."""
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    # Ensure it doesn't start with a digit
    if sanitized and sanitized[0].isdigit():
        sanitized = f"part_{sanitized}"
    return sanitized or "unnamed"
