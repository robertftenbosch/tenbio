import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Part(Base):
    __tablename__ = "parts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False, index=True)
    type = Column(String(20), nullable=False, index=True)  # promoter, rbs, terminator, gene
    description = Column(Text, nullable=True)
    sequence = Column(Text, nullable=False)
    organism = Column(String(50), nullable=True, index=True)  # ecoli, yeast, etc.
    source = Column(String(50), nullable=True)  # iGEM, custom, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
