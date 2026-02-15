"""Tests for parts CRUD routes."""

import pytest


class TestCreatePart:
    def test_create_part(self, client, sample_part_data):
        response = client.post("/api/v1/parts", json=sample_part_data)
        assert response.status_code == 201
        data = response.json()

        assert data["name"] == sample_part_data["name"]
        assert data["type"] == sample_part_data["type"]
        assert data["sequence"] == sample_part_data["sequence"]
        assert data["description"] == sample_part_data["description"]
        assert data["organism"] == sample_part_data["organism"]
        assert "id" in data
        assert "created_at" in data

    def test_create_part_minimal(self, client):
        response = client.post(
            "/api/v1/parts",
            json={"name": "minimal", "type": "gene", "sequence": "ATGC"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal"
        assert data["description"] is None
        assert data["organism"] is None

    def test_create_duplicate_name_fails(self, client, sample_part_data):
        client.post("/api/v1/parts", json=sample_part_data)
        response = client.post("/api/v1/parts", json=sample_part_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_missing_required_fields(self, client):
        response = client.post("/api/v1/parts", json={"name": "incomplete"})
        assert response.status_code == 422


class TestListParts:
    def test_list_empty(self, client):
        response = client.get("/api/v1/parts")
        assert response.status_code == 200
        data = response.json()
        assert data["parts"] == []
        assert data["total"] == 0

    def test_list_with_parts(self, client, sample_part_data):
        client.post("/api/v1/parts", json=sample_part_data)
        response = client.get("/api/v1/parts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["parts"]) == 1

    def test_filter_by_type(self, client):
        client.post("/api/v1/parts", json={"name": "p1", "type": "promoter", "sequence": "ATGC"})
        client.post("/api/v1/parts", json={"name": "g1", "type": "gene", "sequence": "GGCC"})

        response = client.get("/api/v1/parts?type=promoter")
        data = response.json()
        assert data["total"] == 1
        assert data["parts"][0]["type"] == "promoter"

    def test_filter_by_organism(self, client):
        client.post("/api/v1/parts", json={"name": "p1", "type": "gene", "sequence": "ATGC", "organism": "ecoli"})
        client.post("/api/v1/parts", json={"name": "p2", "type": "gene", "sequence": "GGCC", "organism": "yeast"})

        response = client.get("/api/v1/parts?organism=ecoli")
        data = response.json()
        assert data["total"] == 1
        assert data["parts"][0]["organism"] == "ecoli"

    def test_search_by_name(self, client):
        client.post("/api/v1/parts", json={"name": "pTac_promoter", "type": "promoter", "sequence": "ATGC"})
        client.post("/api/v1/parts", json={"name": "GFP_gene", "type": "gene", "sequence": "GGCC"})

        response = client.get("/api/v1/parts?search=pTac")
        data = response.json()
        assert data["total"] == 1
        assert "pTac" in data["parts"][0]["name"]

    def test_pagination_skip(self, client):
        for i in range(5):
            client.post("/api/v1/parts", json={"name": f"part_{i}", "type": "gene", "sequence": "ATGC"})

        response = client.get("/api/v1/parts?skip=3&limit=10")
        data = response.json()
        assert len(data["parts"]) == 2
        assert data["total"] == 5

    def test_pagination_limit(self, client):
        for i in range(5):
            client.post("/api/v1/parts", json={"name": f"part_{i}", "type": "gene", "sequence": "ATGC"})

        response = client.get("/api/v1/parts?limit=2")
        data = response.json()
        assert len(data["parts"]) == 2
        assert data["total"] == 5


class TestGetPart:
    def test_get_existing_part(self, client, sample_part_data):
        create_resp = client.post("/api/v1/parts", json=sample_part_data)
        part_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/parts/{part_id}")
        assert response.status_code == 200
        assert response.json()["name"] == sample_part_data["name"]

    def test_get_nonexistent_part(self, client):
        response = client.get("/api/v1/parts/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUpdatePart:
    def test_update_part_name(self, client, sample_part_data):
        create_resp = client.post("/api/v1/parts", json=sample_part_data)
        part_id = create_resp.json()["id"]

        response = client.put(f"/api/v1/parts/{part_id}", json={"name": "pTac_v2"})
        assert response.status_code == 200
        assert response.json()["name"] == "pTac_v2"

    def test_update_part_sequence(self, client, sample_part_data):
        create_resp = client.post("/api/v1/parts", json=sample_part_data)
        part_id = create_resp.json()["id"]

        response = client.put(f"/api/v1/parts/{part_id}", json={"sequence": "NEWSEQ"})
        assert response.status_code == 200
        assert response.json()["sequence"] == "NEWSEQ"
        # Other fields unchanged
        assert response.json()["name"] == sample_part_data["name"]

    def test_update_nonexistent_part(self, client):
        response = client.put("/api/v1/parts/nonexistent", json={"name": "test"})
        assert response.status_code == 404

    def test_update_duplicate_name_fails(self, client, sample_part_data):
        client.post("/api/v1/parts", json=sample_part_data)
        create_resp = client.post(
            "/api/v1/parts",
            json={**sample_part_data, "name": "other_part"},
        )
        part_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/parts/{part_id}",
            json={"name": sample_part_data["name"]},
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestDeletePart:
    def test_delete_part(self, client, sample_part_data):
        create_resp = client.post("/api/v1/parts", json=sample_part_data)
        part_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/parts/{part_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_resp = client.get(f"/api/v1/parts/{part_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_part(self, client):
        response = client.delete("/api/v1/parts/nonexistent")
        assert response.status_code == 404

    def test_delete_reduces_count(self, client, sample_part_data):
        create_resp = client.post("/api/v1/parts", json=sample_part_data)
        part_id = create_resp.json()["id"]

        list_resp = client.get("/api/v1/parts")
        assert list_resp.json()["total"] == 1

        client.delete(f"/api/v1/parts/{part_id}")

        list_resp = client.get("/api/v1/parts")
        assert list_resp.json()["total"] == 0
