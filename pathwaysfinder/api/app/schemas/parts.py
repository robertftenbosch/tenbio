from datetime import datetime
from pydantic import BaseModel


class PartBase(BaseModel):
    name: str
    type: str
    description: str | None = None
    sequence: str
    organism: str | None = None
    source: str | None = None


class PartCreate(PartBase):
    pass


class PartResponse(PartBase):
    id: str
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class PartListResponse(BaseModel):
    parts: list[PartResponse]
    total: int


class PaperResponse(BaseModel):
    pmid: str | None = None
    title: str | None = None
    authors: list[str] = []
    abstract: str | None = None
    journal: str | None = None
    year: str | None = None
    doi: str | None = None
    doi_url: str | None = None
    url: str | None = None


class PapersListResponse(BaseModel):
    papers: list[PaperResponse]
    query: str
