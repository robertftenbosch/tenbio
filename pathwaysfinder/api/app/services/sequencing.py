"""Sequencing file parsing and alignment service."""

import io
import difflib

from Bio import SeqIO


def parse_sequencing_file(file_content: bytes, filename: str) -> dict:
    """
    Parse a FASTQ or AB1 sequencing file.

    Args:
        file_content: Raw file bytes
        filename: Original filename (used to determine format)

    Returns:
        Dict with sequence, quality_scores, avg_quality, format, read_name, etc.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext in ("fastq", "fq"):
        return _parse_fastq(file_content)
    elif ext in ("ab1", "abi"):
        return _parse_ab1(file_content)
    else:
        raise ValueError(
            f"Unsupported file format: .{ext}. Supported: .fastq, .fq, .ab1, .abi"
        )


def _parse_fastq(file_content: bytes) -> dict:
    """Parse FASTQ file, returning first read."""
    handle = io.StringIO(file_content.decode("utf-8"))
    records = list(SeqIO.parse(handle, "fastq"))

    if not records:
        raise ValueError("No reads found in FASTQ file")

    record = records[0]
    quality_scores = record.letter_annotations.get("phred_quality", [])
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    return {
        "sequence": str(record.seq),
        "quality_scores": quality_scores,
        "avg_quality": round(avg_quality, 1),
        "format": "fastq",
        "read_name": record.id,
        "num_reads": len(records),
        "sequence_length": len(record.seq),
    }


def _parse_ab1(file_content: bytes) -> dict:
    """Parse AB1 (Sanger trace) file."""
    handle = io.BytesIO(file_content)
    record = SeqIO.read(handle, "abi")

    quality_scores = record.letter_annotations.get("phred_quality", [])
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    return {
        "sequence": str(record.seq),
        "quality_scores": quality_scores,
        "avg_quality": round(avg_quality, 1),
        "format": "ab1",
        "read_name": record.id,
        "num_reads": 1,
        "sequence_length": len(record.seq),
    }


def align_to_pathway(query_sequence: str, pathway_parts: list[dict]) -> dict:
    """
    Align a sequencing read against a pathway's concatenated reference.

    Args:
        query_sequence: The sequencing read
        pathway_parts: List of dicts with keys: name, type, sequence

    Returns:
        Dict with overall_similarity, coverage_percent, per-part results
    """
    # Build reference from concatenated parts
    reference = "".join(p["sequence"] for p in pathway_parts)

    if not reference:
        raise ValueError("Pathway has no sequence to align against")

    query_upper = query_sequence.upper()
    ref_upper = reference.upper()

    # Overall similarity using SequenceMatcher
    matcher = difflib.SequenceMatcher(None, query_upper, ref_upper)
    overall_similarity = matcher.ratio() * 100

    # Matching bases (sum of matching block sizes)
    matching_bases = sum(block.size for block in matcher.get_matching_blocks())

    coverage_percent = (matching_bases / len(ref_upper)) * 100 if ref_upper else 0

    # Per-part alignment
    part_results = []
    ref_pos = 0
    for part in pathway_parts:
        part_seq = part["sequence"].upper()
        part_len = len(part_seq)

        # Extract corresponding region from query
        query_region = query_upper[ref_pos : ref_pos + part_len]

        if query_region and part_seq:
            part_matcher = difflib.SequenceMatcher(None, query_region, part_seq)
            part_similarity = part_matcher.ratio() * 100
        else:
            part_similarity = 0.0

        part_results.append(
            {
                "name": part["name"],
                "type": part.get("type", ""),
                "length": part_len,
                "similarity": round(part_similarity, 1),
            }
        )
        ref_pos += part_len

    return {
        "overall_similarity": round(overall_similarity, 1),
        "coverage_percent": round(coverage_percent, 1),
        "matching_bases": matching_bases,
        "reference_length": len(ref_upper),
        "query_length": len(query_upper),
        "part_results": part_results,
    }
