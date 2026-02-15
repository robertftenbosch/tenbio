"""Tests for sequencing import service and route."""

import io
import pytest

from app.services.sequencing import parse_sequencing_file, align_to_pathway


# --- Helpers ---


def make_fastq(read_name="read1", sequence="ATGCATGCATGC", quality=None):
    """Generate a minimal FASTQ file as bytes."""
    if quality is None:
        quality = "I" * len(sequence)  # Phred ~40
    content = f"@{read_name}\n{sequence}\n+\n{quality}\n"
    return content.encode("utf-8")


def make_fastq_multi(reads):
    """Generate a multi-read FASTQ file as bytes."""
    lines = []
    for name, seq, qual in reads:
        lines.extend([f"@{name}", seq, "+", qual])
    return "\n".join(lines).encode("utf-8")


# --- Unit tests for parse_sequencing_file ---


class TestParseSequencingFile:
    def test_parse_fastq_basic(self):
        content = make_fastq(read_name="test_read", sequence="ATGCATGC")
        result = parse_sequencing_file(content, "sample.fastq")

        assert result["sequence"] == "ATGCATGC"
        assert result["format"] == "fastq"
        assert result["read_name"] == "test_read"
        assert result["sequence_length"] == 8
        assert result["num_reads"] >= 1
        assert isinstance(result["avg_quality"], float)

    def test_parse_fastq_fq_extension(self):
        content = make_fastq()
        result = parse_sequencing_file(content, "sample.fq")
        assert result["format"] == "fastq"

    def test_parse_fastq_quality_scores(self):
        # '!' = Phred 0, 'I' = Phred 40
        content = make_fastq(sequence="ATGC", quality="!5II")
        result = parse_sequencing_file(content, "test.fastq")
        assert result["avg_quality"] > 0
        assert len(result["quality_scores"]) == 4

    def test_parse_fastq_takes_first_read(self):
        content = make_fastq_multi([
            ("read1", "ATGC", "IIII"),
            ("read2", "GGCC", "IIII"),
        ])
        result = parse_sequencing_file(content, "multi.fastq")
        assert result["read_name"] == "read1"
        assert result["sequence"] == "ATGC"
        assert result["num_reads"] == 2

    def test_parse_fastq_empty_file(self):
        with pytest.raises(ValueError, match="No reads found"):
            parse_sequencing_file(b"", "empty.fastq")

    def test_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_sequencing_file(b"data", "file.txt")

    def test_unsupported_extension_csv(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_sequencing_file(b"data", "file.csv")

    def test_no_extension(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_sequencing_file(b"data", "noext")


# --- Unit tests for align_to_pathway ---


class TestAlignToPathway:
    def test_perfect_match(self):
        parts = [
            {"name": "p1", "type": "promoter", "sequence": "ATGC"},
            {"name": "p2", "type": "gene", "sequence": "GGCC"},
        ]
        result = align_to_pathway("ATGCGGCC", parts)

        assert result["overall_similarity"] == 100.0
        assert result["coverage_percent"] == 100.0
        assert result["matching_bases"] == 8
        assert result["reference_length"] == 8
        assert result["query_length"] == 8
        assert len(result["part_results"]) == 2
        assert result["part_results"][0]["similarity"] == 100.0
        assert result["part_results"][1]["similarity"] == 100.0

    def test_partial_match(self):
        parts = [{"name": "p1", "type": "gene", "sequence": "ATGCATGC"}]
        # Change half the bases
        result = align_to_pathway("ATGCGGGG", parts)

        assert result["overall_similarity"] < 100.0
        assert result["overall_similarity"] > 0.0

    def test_no_match(self):
        parts = [{"name": "p1", "type": "gene", "sequence": "AAAA"}]
        result = align_to_pathway("TTTT", parts)

        assert result["overall_similarity"] < 100.0

    def test_case_insensitive(self):
        parts = [{"name": "p1", "type": "gene", "sequence": "atgc"}]
        result = align_to_pathway("ATGC", parts)

        assert result["overall_similarity"] == 100.0

    def test_per_part_results(self, sample_pathway_parts):
        full_seq = "".join(p["sequence"] for p in sample_pathway_parts)
        result = align_to_pathway(full_seq, sample_pathway_parts)

        assert len(result["part_results"]) == 4
        for pr in result["part_results"]:
            assert "name" in pr
            assert "type" in pr
            assert "length" in pr
            assert "similarity" in pr
            assert pr["similarity"] == 100.0

    def test_empty_reference_raises(self):
        with pytest.raises(ValueError, match="no sequence"):
            align_to_pathway("ATGC", [])

    def test_empty_parts_sequence(self):
        with pytest.raises(ValueError, match="no sequence"):
            align_to_pathway("ATGC", [{"name": "e", "type": "gene", "sequence": ""}])


# --- Integration tests for route ---


class TestSequencingImportRoute:
    def test_upload_fastq(self, client):
        content = make_fastq(read_name="my_read", sequence="ATGCATGCATGC")
        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("sample.fastq", io.BytesIO(content), "application/octet-stream")},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["parse_result"]["sequence"] == "ATGCATGCATGC"
        assert data["parse_result"]["format"] == "fastq"
        assert data["parse_result"]["read_name"] == "my_read"
        assert data["parse_result"]["sequence_length"] == 12
        assert data["alignment"] is None

    def test_upload_fastq_with_alignment(self, client, sample_pathway_parts):
        full_seq = "".join(p["sequence"] for p in sample_pathway_parts)
        content = make_fastq(sequence=full_seq)
        import json

        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("sample.fastq", io.BytesIO(content), "application/octet-stream")},
            data={"pathway_parts_json": json.dumps(sample_pathway_parts)},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["parse_result"]["sequence"] == full_seq
        assert data["alignment"] is not None
        assert data["alignment"]["overall_similarity"] == 100.0
        assert len(data["alignment"]["part_results"]) == 4

    def test_upload_unsupported_format(self, client):
        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("sample.txt", io.BytesIO(b"data"), "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]

    def test_upload_empty_fastq(self, client):
        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("empty.fastq", io.BytesIO(b""), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_upload_invalid_pathway_json(self, client):
        content = make_fastq()
        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("s.fastq", io.BytesIO(content), "application/octet-stream")},
            data={"pathway_parts_json": "not valid json{{{"},
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_upload_no_file(self, client):
        response = client.post("/api/v1/import/sequencing")
        assert response.status_code == 422

    def test_upload_fq_extension(self, client):
        content = make_fastq(sequence="GGCCTTAA")
        response = client.post(
            "/api/v1/import/sequencing",
            files={"file": ("reads.fq", io.BytesIO(content), "application/octet-stream")},
        )
        assert response.status_code == 200
        assert response.json()["parse_result"]["sequence"] == "GGCCTTAA"
