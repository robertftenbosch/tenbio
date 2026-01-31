"""Codon optimization service for different host organisms."""

from typing import Literal
import random

# Codon usage tables (frequency-based)
# Values represent relative frequency of each codon for the amino acid
# Source: Kazusa codon usage database

CODON_TABLES = {
    "ecoli": {
        # Phenylalanine
        "F": {"TTT": 0.58, "TTC": 0.42},
        # Leucine
        "L": {"TTA": 0.14, "TTG": 0.13, "CTT": 0.12, "CTC": 0.10, "CTA": 0.04, "CTG": 0.47},
        # Isoleucine
        "I": {"ATT": 0.49, "ATC": 0.39, "ATA": 0.11},
        # Methionine (start)
        "M": {"ATG": 1.0},
        # Valine
        "V": {"GTT": 0.28, "GTC": 0.20, "GTA": 0.17, "GTG": 0.35},
        # Serine
        "S": {"TCT": 0.17, "TCC": 0.15, "TCA": 0.14, "TCG": 0.14, "AGT": 0.16, "AGC": 0.25},
        # Proline
        "P": {"CCT": 0.18, "CCC": 0.13, "CCA": 0.20, "CCG": 0.49},
        # Threonine
        "T": {"ACT": 0.19, "ACC": 0.40, "ACA": 0.17, "ACG": 0.25},
        # Alanine
        "A": {"GCT": 0.18, "GCC": 0.26, "GCA": 0.23, "GCG": 0.33},
        # Tyrosine
        "Y": {"TAT": 0.59, "TAC": 0.41},
        # Histidine
        "H": {"CAT": 0.57, "CAC": 0.43},
        # Glutamine
        "Q": {"CAA": 0.34, "CAG": 0.66},
        # Asparagine
        "N": {"AAT": 0.49, "AAC": 0.51},
        # Lysine
        "K": {"AAA": 0.74, "AAG": 0.26},
        # Aspartic acid
        "D": {"GAT": 0.63, "GAC": 0.37},
        # Glutamic acid
        "E": {"GAA": 0.68, "GAG": 0.32},
        # Cysteine
        "C": {"TGT": 0.46, "TGC": 0.54},
        # Tryptophan
        "W": {"TGG": 1.0},
        # Arginine
        "R": {"CGT": 0.36, "CGC": 0.36, "CGA": 0.07, "CGG": 0.11, "AGA": 0.07, "AGG": 0.04},
        # Glycine
        "G": {"GGT": 0.35, "GGC": 0.37, "GGA": 0.13, "GGG": 0.15},
        # Stop
        "*": {"TAA": 0.61, "TAG": 0.09, "TGA": 0.30},
    },
    "yeast": {
        # Phenylalanine
        "F": {"TTT": 0.59, "TTC": 0.41},
        # Leucine
        "L": {"TTA": 0.28, "TTG": 0.29, "CTT": 0.13, "CTC": 0.06, "CTA": 0.14, "CTG": 0.11},
        # Isoleucine
        "I": {"ATT": 0.46, "ATC": 0.26, "ATA": 0.27},
        # Methionine
        "M": {"ATG": 1.0},
        # Valine
        "V": {"GTT": 0.39, "GTC": 0.21, "GTA": 0.21, "GTG": 0.19},
        # Serine
        "S": {"TCT": 0.26, "TCC": 0.16, "TCA": 0.21, "TCG": 0.10, "AGT": 0.16, "AGC": 0.11},
        # Proline
        "P": {"CCT": 0.31, "CCC": 0.15, "CCA": 0.42, "CCG": 0.12},
        # Threonine
        "T": {"ACT": 0.35, "ACC": 0.22, "ACA": 0.30, "ACG": 0.14},
        # Alanine
        "A": {"GCT": 0.38, "GCC": 0.22, "GCA": 0.29, "GCG": 0.11},
        # Tyrosine
        "Y": {"TAT": 0.56, "TAC": 0.44},
        # Histidine
        "H": {"CAT": 0.64, "CAC": 0.36},
        # Glutamine
        "Q": {"CAA": 0.69, "CAG": 0.31},
        # Asparagine
        "N": {"AAT": 0.59, "AAC": 0.41},
        # Lysine
        "K": {"AAA": 0.58, "AAG": 0.42},
        # Aspartic acid
        "D": {"GAT": 0.65, "GAC": 0.35},
        # Glutamic acid
        "E": {"GAA": 0.70, "GAG": 0.30},
        # Cysteine
        "C": {"TGT": 0.63, "TGC": 0.37},
        # Tryptophan
        "W": {"TGG": 1.0},
        # Arginine
        "R": {"CGT": 0.14, "CGC": 0.06, "CGA": 0.07, "CGG": 0.04, "AGA": 0.48, "AGG": 0.21},
        # Glycine
        "G": {"GGT": 0.47, "GGC": 0.19, "GGA": 0.22, "GGG": 0.12},
        # Stop
        "*": {"TAA": 0.48, "TAG": 0.24, "TGA": 0.29},
    },
}

# Standard genetic code (codon to amino acid)
CODON_TO_AA = {
    "TTT": "F", "TTC": "F",
    "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I",
    "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S", "AGT": "S", "AGC": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y",
    "TAA": "*", "TAG": "*", "TGA": "*",
    "CAT": "H", "CAC": "H",
    "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N",
    "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D",
    "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C",
    "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

Organism = Literal["ecoli", "yeast"]


def translate_dna(dna_sequence: str) -> str:
    """Translate DNA sequence to protein sequence."""
    dna = dna_sequence.upper().replace(" ", "").replace("\n", "")
    protein = []

    for i in range(0, len(dna) - 2, 3):
        codon = dna[i:i+3]
        aa = CODON_TO_AA.get(codon, "X")
        if aa == "*":
            break
        protein.append(aa)

    return "".join(protein)


def optimize_codon(amino_acid: str, organism: Organism, strategy: str = "most_frequent") -> str:
    """
    Select optimal codon for an amino acid based on organism codon usage.

    Strategies:
    - most_frequent: Always use the most frequent codon
    - weighted: Randomly select based on frequency weights
    """
    codon_table = CODON_TABLES.get(organism, CODON_TABLES["ecoli"])
    codons = codon_table.get(amino_acid, {})

    if not codons:
        raise ValueError(f"Unknown amino acid: {amino_acid}")

    if strategy == "most_frequent":
        return max(codons.items(), key=lambda x: x[1])[0]
    elif strategy == "weighted":
        codons_list = list(codons.keys())
        weights = list(codons.values())
        return random.choices(codons_list, weights=weights)[0]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def optimize_protein_sequence(
    protein_sequence: str,
    organism: Organism = "ecoli",
    strategy: str = "most_frequent",
    add_stop: bool = True,
) -> dict:
    """
    Optimize a protein sequence for expression in target organism.

    Args:
        protein_sequence: Amino acid sequence (single letter codes)
        organism: Target organism ("ecoli" or "yeast")
        strategy: Optimization strategy ("most_frequent" or "weighted")
        add_stop: Whether to add a stop codon at the end

    Returns:
        Dictionary with optimized DNA sequence and metadata
    """
    protein = protein_sequence.upper().replace(" ", "").replace("\n", "")

    # Validate protein sequence
    valid_aa = set(CODON_TABLES["ecoli"].keys()) - {"*"}
    invalid_aa = set(protein) - valid_aa
    if invalid_aa:
        raise ValueError(f"Invalid amino acids in sequence: {invalid_aa}")

    # Optimize each codon
    optimized_codons = []
    for aa in protein:
        codon = optimize_codon(aa, organism, strategy)
        optimized_codons.append(codon)

    # Add stop codon
    if add_stop:
        stop_codon = optimize_codon("*", organism, strategy)
        optimized_codons.append(stop_codon)

    optimized_dna = "".join(optimized_codons)

    # Calculate GC content
    gc_count = optimized_dna.count("G") + optimized_dna.count("C")
    gc_content = (gc_count / len(optimized_dna)) * 100 if optimized_dna else 0

    return {
        "original_protein": protein,
        "optimized_dna": optimized_dna,
        "organism": organism,
        "strategy": strategy,
        "length_bp": len(optimized_dna),
        "length_aa": len(protein),
        "gc_content": round(gc_content, 1),
    }


def optimize_dna_sequence(
    dna_sequence: str,
    organism: Organism = "ecoli",
    strategy: str = "most_frequent",
) -> dict:
    """
    Re-optimize an existing DNA sequence for a different organism.
    First translates to protein, then optimizes codons.

    Args:
        dna_sequence: DNA sequence to optimize
        organism: Target organism
        strategy: Optimization strategy

    Returns:
        Dictionary with original and optimized sequences
    """
    dna = dna_sequence.upper().replace(" ", "").replace("\n", "")

    # Translate to protein
    protein = translate_dna(dna)

    if not protein:
        raise ValueError("Could not translate DNA sequence to protein")

    # Optimize for target organism
    result = optimize_protein_sequence(protein, organism, strategy, add_stop=True)
    result["original_dna"] = dna
    result["original_length_bp"] = len(dna)

    # Calculate codon adaptation index approximation
    # (simplified - counts how many codons are optimal)
    original_codons = [dna[i:i+3] for i in range(0, len(dna) - 2, 3)]
    optimized_codons = [result["optimized_dna"][i:i+3] for i in range(0, len(result["optimized_dna"]) - 2, 3)]

    matching = sum(1 for o, opt in zip(original_codons, optimized_codons) if o == opt)
    result["codons_changed"] = len(original_codons) - matching
    result["codons_unchanged"] = matching

    return result
