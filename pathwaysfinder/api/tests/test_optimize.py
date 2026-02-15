"""Tests for codon optimization service and routes."""

import pytest

from app.services.codon_optimizer import (
    translate_dna,
    optimize_codon,
    optimize_protein_sequence,
    optimize_dna_sequence,
)


# --- Unit tests for service ---


class TestTranslateDna:
    def test_basic_translation(self):
        # ATG=M, GGC=G, TAA=stop
        assert translate_dna("ATGGGCTAA") == "MG"

    def test_stops_at_stop_codon(self):
        assert translate_dna("ATGTAAGGG") == "M"

    def test_empty_sequence(self):
        assert translate_dna("") == ""

    def test_incomplete_codon_ignored(self):
        # Last 2 bases don't form a full codon
        assert translate_dna("ATGGG") == "M"

    def test_case_insensitive(self):
        assert translate_dna("atgggctaa") == "MG"

    def test_whitespace_stripped(self):
        assert translate_dna("ATG GGC TAA") == "MG"

    def test_newlines_stripped(self):
        assert translate_dna("ATG\nGGC\nTAA") == "MG"


class TestOptimizeCodon:
    def test_methionine_always_atg(self):
        assert optimize_codon("M", "ecoli") == "ATG"
        assert optimize_codon("M", "yeast") == "ATG"

    def test_tryptophan_always_tgg(self):
        assert optimize_codon("W", "ecoli") == "TGG"
        assert optimize_codon("W", "yeast") == "TGG"

    def test_most_frequent_returns_consistent(self):
        codon1 = optimize_codon("L", "ecoli", "most_frequent")
        codon2 = optimize_codon("L", "ecoli", "most_frequent")
        assert codon1 == codon2

    def test_weighted_returns_valid_codon(self):
        codon = optimize_codon("L", "ecoli", "weighted")
        assert len(codon) == 3
        assert codon in {"TTA", "TTG", "CTT", "CTC", "CTA", "CTG"}

    def test_unknown_amino_acid_raises(self):
        with pytest.raises(ValueError, match="Unknown amino acid"):
            optimize_codon("Z", "ecoli")

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            optimize_codon("M", "ecoli", "invalid")

    def test_ecoli_and_yeast_differ(self):
        """Leucine codon preferences differ between organisms."""
        ecoli = optimize_codon("L", "ecoli", "most_frequent")
        yeast = optimize_codon("L", "yeast", "most_frequent")
        # CTG most frequent in ecoli, TTG in yeast
        assert ecoli == "CTG"
        assert yeast == "TTG"


class TestOptimizeProteinSequence:
    def test_basic_optimization(self):
        result = optimize_protein_sequence("MG", organism="ecoli")
        assert result["original_protein"] == "MG"
        assert result["organism"] == "ecoli"
        assert result["length_aa"] == 2
        # ATG + best G codon + stop = 9 bp
        assert result["length_bp"] == 9
        assert 0 <= result["gc_content"] <= 100

    def test_adds_stop_codon(self):
        result = optimize_protein_sequence("M", organism="ecoli", add_stop=True)
        dna = result["optimized_dna"]
        last_codon = dna[-3:]
        assert last_codon in {"TAA", "TAG", "TGA"}

    def test_no_stop_codon(self):
        result = optimize_protein_sequence("M", organism="ecoli", add_stop=False)
        assert result["optimized_dna"] == "ATG"
        assert result["length_bp"] == 3

    def test_invalid_amino_acid_raises(self):
        with pytest.raises(ValueError, match="Invalid amino acids"):
            optimize_protein_sequence("MZX", organism="ecoli")

    def test_yeast_optimization(self):
        result = optimize_protein_sequence("MG", organism="yeast")
        assert result["organism"] == "yeast"

    def test_gc_content_reasonable(self):
        result = optimize_protein_sequence("MAGKL", organism="ecoli")
        assert 20 <= result["gc_content"] <= 80


class TestOptimizeDnaSequence:
    def test_basic_reoptimization(self):
        result = optimize_dna_sequence("ATGGGCTAA", organism="ecoli")
        assert result["original_dna"] == "ATGGGCTAA"
        assert result["original_length_bp"] == 9
        assert "optimized_dna" in result
        assert "codons_changed" in result
        assert "codons_unchanged" in result

    def test_empty_protein_raises(self):
        """A stop-only sequence produces empty protein."""
        with pytest.raises(ValueError, match="Could not translate"):
            optimize_dna_sequence("TAATAATAA", organism="ecoli")

    def test_codons_changed_count(self):
        result = optimize_dna_sequence("ATGGGCTAA", organism="ecoli")
        total = result["codons_changed"] + result["codons_unchanged"]
        assert total >= 1


# --- Integration tests for routes ---


class TestOptimizeProteinRoute:
    def test_optimize_protein(self, client):
        response = client.post(
            "/api/v1/optimize/protein",
            json={"sequence": "MG", "organism": "ecoli", "strategy": "most_frequent"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["original_protein"] == "MG"
        assert data["organism"] == "ecoli"
        assert len(data["optimized_dna"]) > 0

    def test_optimize_protein_yeast(self, client):
        response = client.post(
            "/api/v1/optimize/protein",
            json={"sequence": "MG", "organism": "yeast"},
        )
        assert response.status_code == 200
        assert response.json()["organism"] == "yeast"

    def test_optimize_protein_invalid_sequence(self, client):
        response = client.post(
            "/api/v1/optimize/protein",
            json={"sequence": "XZJ", "organism": "ecoli"},
        )
        assert response.status_code == 400

    def test_optimize_protein_defaults(self, client):
        response = client.post(
            "/api/v1/optimize/protein",
            json={"sequence": "MAGKL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["organism"] == "ecoli"
        assert data["strategy"] == "most_frequent"


class TestOptimizeDnaRoute:
    def test_optimize_dna(self, client):
        response = client.post(
            "/api/v1/optimize/dna",
            json={"sequence": "ATGGGCTAA", "organism": "ecoli"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["original_dna"] == "ATGGGCTAA"
        assert data["codons_changed"] is not None

    def test_optimize_dna_invalid(self, client):
        response = client.post(
            "/api/v1/optimize/dna",
            json={"sequence": "TAATAATAA", "organism": "ecoli"},
        )
        assert response.status_code == 400


class TestTranslateRoute:
    def test_translate(self, client):
        response = client.post(
            "/api/v1/optimize/translate",
            json={"sequence": "ATGGGCTAA"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["protein_sequence"] == "MG"
        assert data["length_aa"] == 2

    def test_translate_empty(self, client):
        response = client.post(
            "/api/v1/optimize/translate",
            json={"sequence": "TAA"},
        )
        assert response.status_code == 400
