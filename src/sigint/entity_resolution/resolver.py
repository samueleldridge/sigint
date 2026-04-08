"""Cascading entity resolver orchestrating match strategies."""

from __future__ import annotations

import structlog

from sigint.entity_resolution.exact import ExactMatchStrategy
from sigint.entity_resolution.fuzzy import FuzzyMatchStrategy
from sigint.entity_resolution.models import (
    Entity,
    EntityType,
    MatchResult,
    ResolutionRequest,
)
from sigint.entity_resolution.rules import RulesMatchStrategy
from sigint.entity_resolution.semantic import SemanticMatchStrategy

logger = structlog.get_logger(__name__)


class EntityResolver:
    """Resolve messy real-world names to canonical entities via a cascading strategy.

    The cascade tries strategies in order and short-circuits on the first
    confident match:  exact → rules → fuzzy → semantic.
    """

    def __init__(
        self,
        entities: list[Entity],
        embeddings: dict[int, list[float]] | None = None,
        *,
        fuzzy_threshold: float = 85.0,
        semantic_threshold: float = 0.82,
        abbreviation_map: dict[str, str] | None = None,
        fred_series_map: dict[str, str] | None = None,
        embed_fn: object | None = None,
    ) -> None:
        self._exact = ExactMatchStrategy(entities)
        self._rules = RulesMatchStrategy(
            entities,
            abbreviation_map=abbreviation_map,
            fred_series_map=fred_series_map,
        )
        self._fuzzy = FuzzyMatchStrategy(entities, threshold=fuzzy_threshold)

        self._semantic: SemanticMatchStrategy | None = None
        if embeddings:
            self._semantic = SemanticMatchStrategy(
                entities,
                embeddings,
                embed_fn=embed_fn,  # type: ignore[arg-type]
                threshold=semantic_threshold,
            )

    def resolve(
        self,
        name: str,
        entity_type_hint: EntityType | None = None,
    ) -> MatchResult | None:
        """Resolve a name through the cascade. Returns None if no match found."""
        request = ResolutionRequest(
            query_name=name,
            entity_type_hint=entity_type_hint,
        )

        # 1. Exact normalised match
        result = self._exact.resolve(request)
        if result is not None:
            logger.debug("entity_resolved", strategy="exact", name=name)
            return result

        # 2. Rule-based match (tickers, abbreviations, FRED series)
        result = self._rules.resolve(request)
        if result is not None:
            logger.debug("entity_resolved", strategy="rules", name=name)
            return result

        # 3. Fuzzy match
        result = self._fuzzy.resolve(request)
        if result is not None:
            logger.debug("entity_resolved", strategy="fuzzy", name=name)
            return result

        # 4. Semantic match (only if embeddings were provided)
        if self._semantic is not None:
            result = self._semantic.resolve(request)
            if result is not None:
                logger.debug("entity_resolved", strategy="semantic", name=name)
                return result

        logger.info("entity_unresolved", name=name)
        return None
