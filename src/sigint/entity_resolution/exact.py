"""Exact match strategy with name normalisation."""

from __future__ import annotations

import re

import structlog

from sigint.entity_resolution.models import Entity, MatchResult, ResolutionRequest

logger = structlog.get_logger(__name__)

# Legal suffixes stripped during normalisation, ordered longest-first
# so "& Co." is removed before "Co."
LEGAL_SUFFIXES: list[str] = [
    "& co.",
    "holdings",
    "group",
    "corp.",
    "corp",
    "inc.",
    "inc",
    "llc",
    "ltd.",
    "ltd",
    "plc",
    "l.p.",
    "n.a.",
    "s.a.",
    "co.",
    "ag",
    "se",
    "nv",
]

_MULTI_SPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Lowercase, strip legal suffixes, collapse whitespace, strip 'The'."""
    result = name.lower().strip()

    # Strip leading "the "
    if result.startswith("the "):
        result = result[4:]

    # Strip trailing legal suffixes (may need multiple passes for
    # names like "Goldman Sachs Group, Inc.")
    changed = True
    while changed:
        changed = False
        result = result.rstrip(" ,")
        for suffix in LEGAL_SUFFIXES:
            if result == suffix or result.endswith(" " + suffix) or result.endswith("," + suffix):
                result = result[: -len(suffix)]
                changed = True

    result = _MULTI_SPACE.sub(" ", result).strip()
    return result


class ExactMatchStrategy:
    """Exact lookup after normalising both the query and stored names."""

    def __init__(self, entities: list[Entity]) -> None:
        self._index: dict[str, Entity] = {}
        for entity in entities:
            self._put(normalize_name(entity.canonical_name), entity)
            for alias in entity.aliases:
                self._put(normalize_name(alias), entity)

    def _put(self, normalised: str, entity: Entity) -> None:
        """Insert into the index, warning on collision."""
        existing = self._index.get(normalised)
        if existing is not None and existing.id != entity.id:
            logger.warning(
                "alias_collision",
                alias=normalised,
                existing=existing.canonical_name,
                new=entity.canonical_name,
            )
        self._index[normalised] = entity

    def resolve(self, request: ResolutionRequest) -> MatchResult | None:
        """Return an exact match or None."""
        normalised = normalize_name(request.query_name)
        entity = self._index.get(normalised)
        if entity is None:
            return None
        if (
            request.entity_type_hint is not None
            and entity.entity_type != request.entity_type_hint
        ):
            return None
        return MatchResult(
            entity=entity,
            strategy_used="exact",
            confidence=1.0,
            match_details=f"Exact match on normalised name '{normalised}'",
        )
