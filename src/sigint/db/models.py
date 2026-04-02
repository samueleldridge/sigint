"""SQLAlchemy table definitions for schema management and Alembic migrations.

These models are NOT used for runtime queries. All runtime database access
uses raw SQL via asyncpg. These exist solely to define the schema and
generate migrations.
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

metadata = MetaData()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata


class EntityCanonical(Base):
    """Master entity registry."""

    __tablename__ = "entity_canonical"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    ticker: Mapped[str | None] = mapped_column(String(20))
    lei: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(100))
    embedding = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_entity_canonical_embedding",
            embedding,
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class EntityAlias(Base):
    """Known name variants for canonical entities."""

    __tablename__ = "entity_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entity_canonical.id"), nullable=False
    )
    alias_name: Mapped[str] = mapped_column(Text, nullable=False)
    alias_type: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("alias_name", "canonical_id", name="uq_alias_name_canonical_id"),
        Index("ix_entity_aliases_alias_name", "alias_name"),
    )
