"""Entity resolution sub-package."""

from __future__ import annotations

from sigint.entity_resolution.models import Entity, EntityType, MatchResult, ResolutionRequest
from sigint.entity_resolution.resolver import EntityResolver

__all__ = [
    "Entity",
    "EntityResolver",
    "EntityType",
    "MatchResult",
    "ResolutionRequest",
]
