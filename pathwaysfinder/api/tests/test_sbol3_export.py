"""Tests for SBOL3 export service and route."""

import json
import pytest

from app.services.sbol3_export import export_pathway_sbol3, _sanitize_display_id


# --- Unit tests for service ---


class TestSanitizeDisplayId:
    def test_basic_name(self):
        assert _sanitize_display_id("pTac") == "pTac"

    def test_spaces_replaced(self):
        assert _sanitize_display_id("my part") == "my_part"

    def test_special_chars_replaced(self):
        assert _sanitize_display_id("part-1.0") == "part_1_0"

    def test_leading_digit(self):
        result = _sanitize_display_id("123abc")
        assert result.startswith("part_")
        assert "123abc" in result

    def test_empty_string(self):
        assert _sanitize_display_id("") == "unnamed"


class TestExportPathwaySbol3:
    def test_basic_export_jsonld(self, sample_pathway_parts):
        result = export_pathway_sbol3(
            name="test_pathway",
            description="A test pathway",
            parts=sample_pathway_parts,
            file_format="json-ld",
        )
        assert isinstance(result, str)
        assert len(result) > 0
        # JSON-LD should be valid JSON
        parsed = json.loads(result)
        assert parsed is not None

    def test_basic_export_rdfxml(self, sample_pathway_parts):
        result = export_pathway_sbol3(
            name="test_pathway",
            description="A test pathway",
            parts=sample_pathway_parts,
            file_format="rdf-xml",
        )
        assert isinstance(result, str)
        assert len(result) > 0
        # RDF/XML should contain XML tags
        assert "<?xml" in result or "<rdf:RDF" in result

    def test_contains_part_names(self, sample_pathway_parts):
        result = export_pathway_sbol3(
            name="test_pathway",
            description="A test",
            parts=sample_pathway_parts,
            file_format="json-ld",
        )
        for part in sample_pathway_parts:
            assert part["name"] in result

    def test_contains_sequences(self, sample_pathway_parts):
        result = export_pathway_sbol3(
            name="test_pathway",
            description="A test",
            parts=sample_pathway_parts,
            file_format="json-ld",
        )
        for part in sample_pathway_parts:
            assert part["sequence"] in result

    def test_single_part(self):
        result = export_pathway_sbol3(
            name="single",
            description="One part only",
            parts=[{"name": "pTac", "type": "promoter", "sequence": "ATGC", "description": ""}],
            file_format="json-ld",
        )
        assert "pTac" in result

    def test_empty_parts_list(self):
        result = export_pathway_sbol3(
            name="empty",
            description="No parts",
            parts=[],
            file_format="json-ld",
        )
        assert isinstance(result, str)

    def test_duplicate_part_names_get_unique_ids(self):
        parts = [
            {"name": "pTac", "type": "promoter", "sequence": "AATT", "description": ""},
            {"name": "pTac", "type": "promoter", "sequence": "GGCC", "description": ""},
        ]
        result = export_pathway_sbol3(
            name="duplicates",
            description="Duplicate parts",
            parts=parts,
            file_format="json-ld",
        )
        # Both sequences should appear (different indices make unique IDs)
        assert "AATT" in result
        assert "GGCC" in result

    def test_all_part_types_mapped(self, sample_pathway_parts):
        """Ensure all standard part types get SO roles without error."""
        result = export_pathway_sbol3(
            name="all_types",
            description="All types",
            parts=sample_pathway_parts,
            file_format="json-ld",
        )
        assert isinstance(result, str)


# --- Integration tests for route ---


class TestExportSbol3Route:
    def test_export_jsonld(self, client, sample_pathway_parts):
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "name": "my_pathway",
                "description": "Test pathway",
                "parts": sample_pathway_parts,
                "format": "json-ld",
            },
        )
        assert response.status_code == 200
        assert "application/ld+json" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert "my_pathway.jsonld" in response.headers["content-disposition"]

        # Body should be valid JSON-LD
        parsed = json.loads(response.content)
        assert parsed is not None

    def test_export_rdfxml(self, client, sample_pathway_parts):
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "name": "my_pathway",
                "description": "Test pathway",
                "parts": sample_pathway_parts,
                "format": "rdf-xml",
            },
        )
        assert response.status_code == 200
        assert "application/rdf+xml" in response.headers["content-type"]
        assert "my_pathway.xml" in response.headers["content-disposition"]

    def test_export_default_format(self, client, sample_pathway_parts):
        """Default format should be json-ld."""
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "name": "default_fmt",
                "description": "",
                "parts": sample_pathway_parts,
            },
        )
        assert response.status_code == 200
        assert "application/ld+json" in response.headers["content-type"]

    def test_export_empty_parts(self, client):
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "name": "empty",
                "description": "No parts",
                "parts": [],
                "format": "json-ld",
            },
        )
        assert response.status_code == 200

    def test_export_missing_name_fails(self, client):
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "description": "Missing name",
                "parts": [],
                "format": "json-ld",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_export_invalid_format(self, client, sample_pathway_parts):
        response = client.post(
            "/api/v1/export/sbol3",
            json={
                "name": "test",
                "description": "",
                "parts": sample_pathway_parts,
                "format": "invalid",
            },
        )
        assert response.status_code == 422
