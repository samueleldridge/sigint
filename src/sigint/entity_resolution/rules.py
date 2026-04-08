"""Rule-based matching strategy for known aliases and tickers."""

from __future__ import annotations

from sigint.entity_resolution.models import Entity, MatchResult, ResolutionRequest

# Well-known abbreviation → canonical name mappings
DEFAULT_ABBREVIATIONS: dict[str, str] = {
    "gs": "Goldman Sachs",
    "jpm": "JPMorgan Chase",
    "ms": "Morgan Stanley",
    "bofa": "Bank of America",
    "bac": "Bank of America",
    "aapl": "Apple",
    "msft": "Microsoft",
    "goog": "Alphabet",
    "googl": "Alphabet",
    "amzn": "Amazon",
    "meta": "Meta Platforms",
    "tsla": "Tesla",
    "nvda": "NVIDIA",
    "ibm": "IBM",
}

# Informal macro series names → FRED series IDs
FRED_SERIES_MAP: dict[str, str] = {
    "fed rate": "FEDFUNDS",
    "fed funds rate": "FEDFUNDS",
    "federal funds rate": "FEDFUNDS",
    "unemployment": "UNRATE",
    "unemployment rate": "UNRATE",
    "cpi": "CPIAUCSL",
    "inflation": "CPIAUCSL",
    "consumer price index": "CPIAUCSL",
    "gdp": "GDP",
    "real gdp": "GDPC1",
    "10y yield": "DGS10",
    "10 year yield": "DGS10",
    "10-year treasury": "DGS10",
    "2y yield": "DGS2",
    "2 year yield": "DGS2",
    "30y mortgage": "MORTGAGE30US",
    "30 year mortgage rate": "MORTGAGE30US",
}


class RulesMatchStrategy:
    """Look up entities via ticker symbols and known abbreviations."""

    def __init__(
        self,
        entities: list[Entity],
        abbreviation_map: dict[str, str] | None = None,
        fred_series_map: dict[str, str] | None = None,
    ) -> None:
        self._abbreviations = {**DEFAULT_ABBREVIATIONS}
        if abbreviation_map:
            self._abbreviations.update(abbreviation_map)

        self._fred_map = {**FRED_SERIES_MAP}
        if fred_series_map:
            self._fred_map.update(fred_series_map)

        # Build ticker → Entity index (case-insensitive)
        self._ticker_index: dict[str, Entity] = {}
        for entity in entities:
            if entity.ticker:
                self._ticker_index[entity.ticker.lower()] = entity

        # Build canonical name (lowered) → Entity index
        self._name_index: dict[str, Entity] = {}
        for entity in entities:
            self._name_index[entity.canonical_name.lower()] = entity

    def resolve(self, request: ResolutionRequest) -> MatchResult | None:
        """Try ticker lookup, then abbreviation map, then FRED series map."""
        query = request.query_name.strip().lower()

        # 1. Direct ticker lookup
        entity = self._ticker_index.get(query)
        if entity is not None:
            if self._type_matches(entity, request):
                return MatchResult(
                    entity=entity,
                    strategy_used="rules",
                    confidence=0.95,
                    match_details=f"Ticker match '{query}' → {entity.canonical_name}",
                )

        # 2. Known abbreviation → canonical name → entity
        canonical = self._abbreviations.get(query)
        if canonical is not None:
            entity = self._name_index.get(canonical.lower())
            if entity is not None and self._type_matches(entity, request):
                return MatchResult(
                    entity=entity,
                    strategy_used="rules",
                    confidence=0.95,
                    match_details=(
                        f"Abbreviation match '{query}' → '{canonical}'"
                    ),
                )

        # 3. FRED series name → series ID entity
        series_id = self._fred_map.get(query)
        if series_id is not None:
            entity = self._name_index.get(series_id.lower())
            if entity is not None and self._type_matches(entity, request):
                return MatchResult(
                    entity=entity,
                    strategy_used="rules",
                    confidence=0.95,
                    match_details=(
                        f"FRED series match '{query}' → '{series_id}'"
                    ),
                )

        return None

    @staticmethod
    def _type_matches(entity: Entity, request: ResolutionRequest) -> bool:
        """Check entity type matches the hint, if one was provided."""
        if request.entity_type_hint is None:
            return True
        return entity.entity_type == request.entity_type_hint
