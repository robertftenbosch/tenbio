"""Seed the database with the Peralta-Yahya 2011 bisabolene constructs as reference pathways.

These are the *canonical* POC plasmids referenced in:

    Peralta-Yahya et al. (2011). Identification and microbial production
    of a terpene-based advanced biofuel. Nature Communications 2:483.
    DOI: 10.1038/ncomms1494

Addgene links:
    pBbA5c-MevT(CO)-T1-MBIS(CO, ispA)  -> https://www.addgene.org/35152/
    pTrcAgBIS (CO)                      -> https://www.addgene.org/35153/

The part sequences below are *placeholders* intentionally kept short so that this
seed runs without external downloads. Before using these pathways for any real
design work, replace the sequence fields with the verified GenBank files from
Addgene (request the plasmid, download the map, import via /api/v1/parts POST,
then swap the part_id references in the pathway).

Run from the api/ directory after Alembic migration:

    python seed_pathways.py
"""

import sys
sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.parts import Part
from app.models.pathway import Pathway, PathwayPart


# ---- Placeholder parts (see docstring; replace with real sequences from Addgene) ----
PLACEHOLDER_PARTS = [
    # MevT operon components — upper mevalonate pathway (acetyl-CoA -> mevalonate)
    {"name": "atoB_ecoli",            "type": "gene",      "description": "Acetoacetyl-CoA thiolase (endogenous E. coli)", "sequence": "ATG" + "N" * 1182,    "organism": "ecoli",  "source": "Martin2003"},
    {"name": "HMGS_sce_ERG13",        "type": "gene",      "description": "HMG-CoA synthase (S. cerevisiae ERG13)",         "sequence": "ATG" + "N" * 1488,    "organism": "ecoli",  "source": "Martin2003"},
    {"name": "tHMGR_sce",             "type": "gene",      "description": "Truncated HMG-CoA reductase (S. cerevisiae)",    "sequence": "ATG" + "N" * 1575,    "organism": "ecoli",  "source": "Martin2003"},
    # MBIS operon — lower mevalonate pathway (mevalonate -> FPP)
    {"name": "MK_sce_ERG12",          "type": "gene",      "description": "Mevalonate kinase (S. cerevisiae ERG12)",        "sequence": "ATG" + "N" * 1332,    "organism": "ecoli",  "source": "Martin2003"},
    {"name": "PMK_sce_ERG8",          "type": "gene",      "description": "Phosphomevalonate kinase (S. cerevisiae ERG8)",  "sequence": "ATG" + "N" * 1353,    "organism": "ecoli",  "source": "Martin2003"},
    {"name": "PMD_sce_MVD1",          "type": "gene",      "description": "Mevalonate diphosphate decarboxylase",           "sequence": "ATG" + "N" * 1263,    "organism": "ecoli",  "source": "Martin2003"},
    {"name": "idi_ecoli",             "type": "gene",      "description": "IPP isomerase (endogenous E. coli)",             "sequence": "ATG" + "N" *  546,    "organism": "ecoli",  "source": "endogenous"},
    {"name": "ispA_ecoli",            "type": "gene",      "description": "FPP synthase (endogenous E. coli)",              "sequence": "ATG" + "N" *  900,    "organism": "ecoli",  "source": "endogenous"},
    # Terpene synthase
    {"name": "AgBIS_CO",              "type": "gene",      "description": "(E)-alpha-bisabolene synthase from Abies grandis, codon-optimized for E. coli", "sequence": "ATG" + "N" * 2520, "organism": "ecoli", "source": "Peralta-Yahya2011"},
    # Promoters / RBS / terminators used by the pBbx backbones
    {"name": "lacUV5_promoter",       "type": "promoter",  "description": "lacUV5 promoter (IPTG-inducible)",               "sequence": "AAATTGTGAGCGGATAACAATTTCACACAGGAAACAGCTATGACCATGATTAC", "organism": "ecoli", "source": "BglBrick"},
    {"name": "Ptrc",                  "type": "promoter",  "description": "Trc hybrid promoter (IPTG-inducible)",           "sequence": "TTGACAATTAATCATCCGGCTCGTATAATGTGTGG", "organism": "ecoli", "source": "BglBrick"},
    {"name": "BBa_B0034",             "type": "rbs",       "description": "Standard RBS, Elowitz 1999",                     "sequence": "AAAGAGGAGAAA",               "organism": "ecoli", "source": "iGEM"},
    {"name": "T1_terminator",         "type": "terminator","description": "rrnB T1 terminator",                              "sequence": "AACGCTCGGTTGCCGCCGGGCGTTTTTTAT", "organism": "ecoli", "source": "BglBrick"},
]


# ---- Pathways ----
# We reference parts by name here and resolve to IDs at insert time.
PATHWAY_DEFINITIONS = [
    {
        "name": "pBbA5c-MevT-MBIS",
        "description": (
            "Upper + lower mevalonate pathway on a p15A-origin, chloramphenicol-resistance plasmid "
            "with lacUV5 promoter. Peralta-Yahya 2011 canonical FPP overproducer."
        ),
        "host_organism": "ecoli",
        "plasmid_backbone": "pBbA5c (p15A, cat)",
        "selection_marker": "chloramphenicol",
        "target_molecule": "bisabolene",
        "source": "Addgene 35152",
        "reference_doi": "10.1038/ncomms1494",
        "notes": (
            "Replace placeholder sequences with the Addgene 35152 GenBank file before use. "
            "Verify with Sanger on junctions after transformation into E. coli DH1."
        ),
        "parts": [
            "lacUV5_promoter", "BBa_B0034", "atoB_ecoli", "BBa_B0034", "HMGS_sce_ERG13",
            "BBa_B0034", "tHMGR_sce", "T1_terminator",
            "lacUV5_promoter", "BBa_B0034", "MK_sce_ERG12", "BBa_B0034", "PMK_sce_ERG8",
            "BBa_B0034", "PMD_sce_MVD1", "BBa_B0034", "idi_ecoli", "BBa_B0034", "ispA_ecoli",
            "T1_terminator",
        ],
    },
    {
        "name": "pTrcAgBIS",
        "description": (
            "Bisabolene synthase (AgBIS, codon-optimized) under Ptrc on a pBR322-origin, "
            "carbenicillin-resistance plasmid. Co-transformed with pBbA5c-MevT-MBIS to produce ~900 mg/L bisabolene."
        ),
        "host_organism": "ecoli",
        "plasmid_backbone": "pTrc (pBR322, bla)",
        "selection_marker": "carbenicillin",
        "target_molecule": "bisabolene",
        "source": "Addgene 35153",
        "reference_doi": "10.1038/ncomms1494",
        "notes": (
            "Co-transform with pBbA5c-MevT-MBIS into E. coli DH1. Induce with 0.1 mM IPTG, "
            "shift to 30 C, add 20 percent v/v dodecane overlay, shake 72-96 h."
        ),
        "parts": [
            "Ptrc", "BBa_B0034", "AgBIS_CO", "T1_terminator",
        ],
    },
]


def _upsert_part(db, part_def: dict) -> Part:
    existing = db.query(Part).filter(Part.name == part_def["name"]).first()
    if existing:
        return existing
    part = Part(**part_def)
    db.add(part)
    db.flush()
    return part


def seed() -> None:
    db = SessionLocal()
    try:
        # Upsert parts
        name_to_part = {pd["name"]: _upsert_part(db, pd) for pd in PLACEHOLDER_PARTS}

        for pdef in PATHWAY_DEFINITIONS:
            if db.query(Pathway).filter(Pathway.name == pdef["name"]).first():
                print(f"  skip existing pathway: {pdef['name']}")
                continue

            pathway = Pathway(
                name=pdef["name"],
                description=pdef["description"],
                host_organism=pdef["host_organism"],
                plasmid_backbone=pdef["plasmid_backbone"],
                selection_marker=pdef["selection_marker"],
                target_molecule=pdef["target_molecule"],
                source=pdef["source"],
                reference_doi=pdef["reference_doi"],
                notes=pdef["notes"],
            )
            for pos, part_name in enumerate(pdef["parts"]):
                part = name_to_part.get(part_name)
                if part is None:
                    raise RuntimeError(f"Missing part definition: {part_name}")
                pathway.pathway_parts.append(PathwayPart(
                    part_id=part.id, position=pos, direction="forward",
                ))
            db.add(pathway)
            print(f"  added pathway: {pdef['name']} ({len(pdef['parts'])} parts)")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
