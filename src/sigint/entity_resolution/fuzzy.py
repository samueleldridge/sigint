"""Fuzzy string matching strategy using rapidfuzz."""

from __future__ import annotations

from rapidfuzz import fuzz, process

from sigint.entity_resolution.models import Entity, MatchResult, ResolutionRequest

DEFAULT_FUZZY_THRESHOLD: float = 85.0


class FuzzyMatchStrategy:
    """Match query against all aliases using rapidfuzz token_sort_ratio."""

    def __init__(
        self,
        entities: list[Entity],
        threshold: float = DEFAULT_FUZZY_THRESHOLD,
    ) -> None:
        self._threshold = threshold

        # Build a flat list of (alias_lower, Entity) pairs for scoring
        self._candidates: list[tuple[str, Entity]] = []
        for entity in entities:
            self._candidates.append((entity.canonical_name.lower(), entity))
            for alias in entity.aliases:
                self._candidates.append((alias.lower(), entity))

        # Separate list of alias strings for process.extractOne
        self._choices = [alias for alias, _ in self._candidates]

    def resolve(self, request: ResolutionRequest) -> MatchResult | None:
        """Return the best fuzzy match above the threshold, or None."""
        query = request.query_name.strip().lower()

        if request.entity_type_hint is not None:
            # Filter to matching entity types and use extractOne on the subset
            filtered = [
                (alias, entity)
                for alias, entity in self._candidates
                if entity.entity_type == request.entity_type_hint
            ]
            if not filtered:
                return None
            choices = [alias for alias, _ in filtered]
            best = process.extractOne(
                query,
                choices,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self._threshold,
            )
            if best is None:
                return None
            best_alias, best_score, best_idx = best
            best_entity = filtered[best_idx][1]
        else:
            best = process.extractOne(
                query,
                self._choices,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self._threshold,
            )
            if best is None:
                return None
            best_alias, best_score, best_idx = best
            best_entity = self._candidates[best_idx][1]

        return MatchResult(
            entity=best_entity,
            strategy_used="fuzzy",
            confidence=round(best_score / 100.0, 4),
            match_details=(
                f"Fuzzy match '{request.query_name}' ~ '{best_alias}' "
                f"(score={best_score:.1f})"
            ),
        )
