"""Export Pathway objects to GenBank and FASTA formats via Biopython.

A Pathway is assembled by concatenating Part sequences in `position` order,
with each Part annotated as a feature. This is lossless w.r.t. your Pathway
model and opens cleanly in SnapGene, Benchling, and ApE.
"""

from io import StringIO
from datetime import datetime

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio import SeqIO


# Map Part.type (lowercase) -> GenBank feature key.
# We fall back to misc_feature for anything unknown.
_FEATURE_KEY_MAP = {
    "promoter": "promoter",
    "rbs": "RBS",
    "gene": "CDS",
    "cds": "CDS",
    "terminator": "terminator",
    "origin": "rep_origin",
    "ori": "rep_origin",
    "marker": "CDS",
    "tag": "misc_feature",
    "scar": "misc_feature",
}


def _feature_key_for(part_type: str | None) -> str:
    if not part_type:
        return "misc_feature"
    return _FEATURE_KEY_MAP.get(part_type.lower(), "misc_feature")


def _reverse_complement(seq: str) -> str:
    return str(Seq(seq).reverse_complement())


def _build_record(pathway) -> SeqRecord:
    """Build a Biopython SeqRecord from a Pathway ORM object."""
    ordered = sorted(pathway.pathway_parts, key=lambda pp: pp.position)

    assembled = []
    features: list[SeqFeature] = []
    cursor = 0

    for pp in ordered:
        part = pp.part
        if not part or not part.sequence:
            continue
        seq = part.sequence.upper().replace(" ", "").replace("\n", "")
        if pp.direction == "reverse":
            seq = _reverse_complement(seq)

        start, end = cursor, cursor + len(seq)
        strand = -1 if pp.direction == "reverse" else 1

        qualifiers = {
            "label": [part.name],
            "note": [f"part_type={part.type}"],
        }
        if part.source:
            qualifiers["note"].append(f"source={part.source}")
        if pp.notes:
            qualifiers["note"].append(f"instance_note={pp.notes}")
        if part.description:
            qualifiers["note"].append(part.description)

        features.append(SeqFeature(
            FeatureLocation(start, end, strand=strand),
            type=_feature_key_for(part.type),
            qualifiers=qualifiers,
        ))
        assembled.append(seq)
        cursor = end

    full_seq = "".join(assembled) or "N"  # Biopython rejects empty sequences
    # Safe name for LOCUS line: no spaces, max 16 chars per GenBank spec,
    # but modern parsers accept longer. We trim to 20 to stay friendly.
    locus = pathway.name.replace(" ", "_")[:20] or "pathway"

    record = SeqRecord(
        Seq(full_seq),
        id=locus,
        name=locus,
        description=pathway.description or f"Pathway {pathway.name}",
        annotations={
            "molecule_type": "DNA",
            "topology": "linear",
            "date": datetime.utcnow().strftime("%d-%b-%Y").upper(),
            "organism": pathway.host_organism or ".",
            "source": pathway.source or "tenbio pathwaysfinder",
            "keywords": [
                pathway.target_molecule or "",
                pathway.plasmid_backbone or "",
            ],
        },
        features=features,
    )
    return record


def pathway_to_genbank(pathway) -> str:
    """Return a GenBank-formatted string for the given Pathway."""
    record = _build_record(pathway)
    buf = StringIO()
    SeqIO.write(record, buf, "genbank")
    return buf.getvalue()


def pathway_to_fasta(pathway) -> str:
    """Return a FASTA-formatted string (single assembled sequence + per-part entries)."""
    record = _build_record(pathway)
    buf = StringIO()
    # Write the assembled construct first
    SeqIO.write(record, buf, "fasta")

    # Then each part as its own FASTA entry for convenience in primer design, etc.
    ordered = sorted(pathway.pathway_parts, key=lambda pp: pp.position)
    for pp in ordered:
        if not pp.part or not pp.part.sequence:
            continue
        seq = pp.part.sequence.upper().replace(" ", "").replace("\n", "")
        if pp.direction == "reverse":
            seq = _reverse_complement(seq)
        part_record = SeqRecord(
            Seq(seq),
            id=f"{pathway.name}__{pp.position:02d}__{pp.part.name}",
            description=f"{pp.part.type} direction={pp.direction}",
        )
        SeqIO.write(part_record, buf, "fasta")

    return buf.getvalue()
