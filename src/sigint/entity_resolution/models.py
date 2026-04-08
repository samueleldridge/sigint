"""Pydantic models for entity resolution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """Supported entity types in the resolution system."""

    COMPANY = "company"
    COUNTRY = "country"
    COMMODITY = "commodity"
    MACRO_SERIES = "macro_series"


class Entity(BaseModel):
    """A canonical entity in the system."""

    id: int
    canonical_name: str
    entity_type: EntityType
    ticker: str | None = None
    lei: str | None = None
    aliases: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    """Result of a successful entity resolution match."""

    entity: Entity
    strategy_used: str
    confidence: float = Field(ge=0.0, le=1.0)
    match_details: str


class ResolutionRequest(BaseModel):
    """Request to resolve a name to a canonical entity."""

    query_name: str
    entity_type_hint: EntityType | None = None
