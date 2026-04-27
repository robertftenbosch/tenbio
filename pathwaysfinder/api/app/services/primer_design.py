"""Gibson Assembly primer design.

Given an ordered list of DNA fragments (e.g. parts of a Pathway), generate
primers that add a homology overlap to each adjacent fragment, suitable for
isothermal Gibson / HiFi assembly.

Design choices (defaults match the NEB HiFi / Gibson standard protocol):
    - Target overlap length:     25 bp (NEB recommends 20-40 bp)
    - Minimum annealing Tm:      60 C (primer body portion only, not the overhang)
    - Max primer length:         60 bp (overhang + anneal)
    - Tm calculation:            Nearest-Neighbor (SantaLucia 1998) via Biopython

We use only Biopython, which is already a dependency, so no new pip installs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from Bio.Seq import Seq
from Bio.SeqUtils import MeltingTemp as mt
from Bio.SeqUtils import gc_fraction


# ------------------------- Config -------------------------

DEFAULT_OVERLAP_BP = 25
DEFAULT_TARGET_TM = 60.0
DEFAULT_TM_TOLERANCE = 3.0
DEFAULT_MIN_ANNEAL_BP = 18
DEFAULT_MAX_ANNEAL_BP = 35
DEFAULT_MAX_TOTAL_BP = 60


# ------------------------- Data classes -------------------------

@dataclass
class PrimerPair:
    fragment_index: int
    fragment_name: str
    forward_primer: str
    reverse_primer: str
    forward_anneal: str       # the 3' portion that anneals to the template
    reverse_anneal: str
    forward_overhang: str     # the 5' overhang providing homology to previous fragment
    reverse_overhang: str     # the 5' overhang providing homology to next fragment
    forward_tm: float         # Tm of the anneal portion only
    reverse_tm: float
    forward_gc: float
    reverse_gc: float
    warnings: list[str]


@dataclass
class PrimerDesignResult:
    primer_pairs: list[PrimerPair]
    global_warnings: list[str]


# ------------------------- Helpers -------------------------

def _clean(seq: str) -> str:
    s = seq.upper().replace(" ", "").replace("\n", "").replace("\r", "")
    allowed = set("ACGTN")
    bad = set(s) - allowed
    if bad:
        raise ValueError(f"Sequence contains non-ACGTN characters: {bad}")
    return s


def _reverse_complement(seq: str) -> str:
    return str(Seq(seq).reverse_complement())


def _tm(seq: str) -> float:
    """Nearest-neighbor Tm. Returns 0 for sequences <6 bp."""
    if len(seq) < 6:
        return 0.0
    return float(mt.Tm_NN(Seq(seq)))


def _find_anneal_region(
    fragment: str,
    end: Literal["5prime", "3prime"],
    target_tm: float,
    tolerance: float,
    min_bp: int,
    max_bp: int,
) -> tuple[str, float, list[str]]:
    """Grow an anneal region from the given end of the fragment until Tm hits target.

    Returns (anneal_sequence, tm, warnings). For 3prime end, the anneal sequence
    returned is the reverse-complement (i.e. already oriented as a primer).
    """
    warnings: list[str] = []

    if end == "5prime":
        # Forward primer anneals to the template; primer sequence == sense strand 5' end
        candidate_builder = lambda n: fragment[:n]  # noqa: E731
    else:
        # Reverse primer is the reverse-complement of the 3' end of the fragment
        candidate_builder = lambda n: _reverse_complement(fragment[-n:])  # noqa: E731

    best = None
    best_diff = float("inf")

    for n in range(min_bp, min(max_bp, len(fragment)) + 1):
        anneal = candidate_builder(n)
        tm = _tm(anneal)
        diff = abs(tm - target_tm)
        if diff < best_diff:
            best_diff = diff
            best = (anneal, tm, n)
        # Stop early once we are within tolerance AND beyond the minimum
        if tm >= target_tm and diff <= tolerance:
            return anneal, tm, warnings

    if best is None:  # shouldn't happen given len checks above
        raise ValueError(f"Fragment too short ({len(fragment)} bp) for anneal design")

    anneal, tm, _n = best
    if abs(tm - target_tm) > tolerance:
        warnings.append(
            f"Could not reach target Tm {target_tm:.1f} C +/- {tolerance:.1f}; "
            f"best achievable is {tm:.1f} C at {_n} bp anneal length."
        )
    return anneal, tm, warnings


# ------------------------- Public API -------------------------

def design_gibson_primers(
    fragments: list[dict],
    circular: bool = False,
    overlap_bp: int = DEFAULT_OVERLAP_BP,
    target_tm: float = DEFAULT_TARGET_TM,
    tm_tolerance: float = DEFAULT_TM_TOLERANCE,
    min_anneal_bp: int = DEFAULT_MIN_ANNEAL_BP,
    max_anneal_bp: int = DEFAULT_MAX_ANNEAL_BP,
) -> PrimerDesignResult:
    """Design primers for Gibson Assembly of the given ordered fragments.

    Args:
        fragments: list of {"name": str, "sequence": str}, in assembly order.
        circular: if True, the last fragment's 3' homology wraps to the first
                  fragment's 5' end (plasmid assembly). If False, the first
                  fragment has no 5' overhang and the last has no 3' overhang
                  (linear product).
        overlap_bp: homology arm length. NEB HiFi recommends 20-40 bp; 25 is a
                    solid default.
        target_tm: target Tm for the annealing portion (not counting overhang).
        tm_tolerance: acceptable deviation from target_tm.
        min_anneal_bp / max_anneal_bp: bounds on the annealing portion length.

    Returns:
        PrimerDesignResult with one PrimerPair per fragment.
    """
    if len(fragments) < 2:
        raise ValueError("Gibson assembly requires at least 2 fragments")

    # Clean + validate
    cleaned = []
    for i, f in enumerate(fragments):
        seq = _clean(f.get("sequence", ""))
        name = f.get("name") or f"fragment_{i}"
        if len(seq) < max(overlap_bp * 2, min_anneal_bp + overlap_bp):
            raise ValueError(
                f"Fragment '{name}' is too short ({len(seq)} bp) for overlap {overlap_bp} bp"
            )
        cleaned.append({"name": name, "sequence": seq})

    n = len(cleaned)
    pairs: list[PrimerPair] = []
    global_warnings: list[str] = []

    for i, frag in enumerate(cleaned):
        seq = frag["sequence"]
        name = frag["name"]
        frag_warnings: list[str] = []

        # Forward primer: overhang from the 3' end of the PREVIOUS fragment + anneal to this fragment's 5' end
        prev_idx = (i - 1) % n if circular else (i - 1)
        if circular or prev_idx >= 0:
            prev_seq = cleaned[prev_idx]["sequence"]
            fwd_overhang = prev_seq[-overlap_bp:]
        else:
            fwd_overhang = ""  # first fragment, linear

        fwd_anneal, fwd_tm, w = _find_anneal_region(
            seq, "5prime", target_tm, tm_tolerance, min_anneal_bp, max_anneal_bp
        )
        frag_warnings.extend(w)
        fwd_primer = fwd_overhang + fwd_anneal

        # Reverse primer: overhang is RC of the 5' end of the NEXT fragment + anneal to this fragment's 3' end
        next_idx = (i + 1) % n if circular else (i + 1)
        if circular or next_idx < n:
            next_seq = cleaned[next_idx]["sequence"]
            rev_overhang = _reverse_complement(next_seq[:overlap_bp])
        else:
            rev_overhang = ""  # last fragment, linear

        rev_anneal, rev_tm, w = _find_anneal_region(
            seq, "3prime", target_tm, tm_tolerance, min_anneal_bp, max_anneal_bp
        )
        frag_warnings.extend(w)
        rev_primer = rev_overhang + rev_anneal

        # Length sanity
        if len(fwd_primer) > DEFAULT_MAX_TOTAL_BP:
            frag_warnings.append(
                f"Forward primer is {len(fwd_primer)} bp (> {DEFAULT_MAX_TOTAL_BP}); "
                "consider a shorter overhang or stricter Tm."
            )
        if len(rev_primer) > DEFAULT_MAX_TOTAL_BP:
            frag_warnings.append(
                f"Reverse primer is {len(rev_primer)} bp (> {DEFAULT_MAX_TOTAL_BP}); "
                "consider a shorter overhang or stricter Tm."
            )

        # Tm balance between forward and reverse
        if abs(fwd_tm - rev_tm) > 4.0:
            frag_warnings.append(
                f"Forward/reverse Tm imbalance: {fwd_tm:.1f} vs {rev_tm:.1f} C (> 4 C)."
            )

        pairs.append(PrimerPair(
            fragment_index=i,
            fragment_name=name,
            forward_primer=fwd_primer,
            reverse_primer=rev_primer,
            forward_anneal=fwd_anneal,
            reverse_anneal=rev_anneal,
            forward_overhang=fwd_overhang,
            reverse_overhang=rev_overhang,
            forward_tm=round(fwd_tm, 1),
            reverse_tm=round(rev_tm, 1),
            forward_gc=round(float(gc_fraction(fwd_anneal)) * 100, 1),
            reverse_gc=round(float(gc_fraction(rev_anneal)) * 100, 1),
            warnings=frag_warnings,
        ))

    return PrimerDesignResult(primer_pairs=pairs, global_warnings=global_warnings)
