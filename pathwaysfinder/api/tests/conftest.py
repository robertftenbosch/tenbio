"""Shared test fixtures for the Pathways API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


# In-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    """FastAPI TestClient with overridden DB dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_part_data():
    """Sample part data for creating test parts."""
    return {
        "name": "pTac",
        "type": "promoter",
        "description": "Tac promoter",
        "sequence": "AATTGTGAGCGGATAACAATT",
        "organism": "ecoli",
        "source": "custom",
    }


@pytest.fixture()
def sample_pathway_parts():
    """Sample pathway parts list for export/alignment tests."""
    return [
        {
            "name": "pTac",
            "type": "promoter",
            "sequence": "AATTGTGAGCGGATAACAATT",
            "description": "Tac promoter",
        },
        {
            "name": "B0034",
            "type": "rbs",
            "sequence": "AAAGAGGAGAAA",
            "description": "RBS",
        },
        {
            "name": "GFP",
            "type": "gene",
            "sequence": "ATGGTGAGCAAGGGCGAGGAG",
            "description": "Green fluorescent protein",
        },
        {
            "name": "B0015",
            "type": "terminator",
            "sequence": "CCAGGCATCAAATAAAACGAAAGGCTCAGTCGAAAGACTGGGCCTTTCGTTTTATCTG",
            "description": "Double terminator",
        },
    ]
