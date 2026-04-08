"""Tests for entity resolution."""

from __future__ import annotations

import pytest

from sigint.entity_resolution.exact import ExactMatchStrategy, normalize_name
from sigint.entity_resolution.fuzzy import FuzzyMatchStrategy
from sigint.entity_resolution.models import Entity, EntityType, ResolutionRequest
from sigint.entity_resolution.resolver import EntityResolver
from sigint.entity_resolution.rules import RulesMatchStrategy
from sigint.entity_resolution.semantic import SemanticMatchStrategy, _cosine_similarity

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_entities() -> list[Entity]:
    """A small set of entities for testing."""
    return [
        Entity(
            id=1,
            canonical_name="Goldman Sachs",
            entity_type=EntityType.COMPANY,
            ticker="GS",
            aliases=["Goldman Sachs Group", "Goldman Sachs & Co. LLC"],
        ),
        Entity(
            id=2,
            canonical_name="JPMorgan Chase",
            entity_type=EntityType.COMPANY,
            ticker="JPM",
            aliases=["JP Morgan", "JPMorgan", "J.P. Morgan Chase & Co."],
        ),
        Entity(
            id=3,
            canonical_name="Apple",
            entity_type=EntityType.COMPANY,
            ticker="AAPL",
            aliases=["Apple Inc.", "Apple Inc"],
        ),
        Entity(
            id=4,
            canonical_name="FEDFUNDS",
            entity_type=EntityType.MACRO_SERIES,
            aliases=["Federal Funds Effective Rate"],
        ),
        Entity(
            id=5,
            canonical_name="Tesla",
            entity_type=EntityType.COMPANY,
            ticker="TSLA",
            aliases=["Tesla Inc.", "Tesla Motors"],
        ),
        Entity(
            id=6,
            canonical_name="United States",
            entity_type=EntityType.COUNTRY,
            aliases=["USA", "US", "United States of America"],
        ),
        Entity(
            id=7,
            canonical_name="Morgan Stanley",
            entity_type=EntityType.COMPANY,
            ticker="MS",
            aliases=["Morgan Stanley & Co. LLC"],
        ),
    ]


# ---------------------------------------------------------------------------
# normalize_name tests
# ---------------------------------------------------------------------------

class TestNormalizeName:
    """Tests for the name normalisation function."""

    def test_lowercase(self) -> None:
        assert normalize_name("GOLDMAN SACHS") == "goldman sachs"

    def test_strip_inc(self) -> None:
        assert normalize_name("Apple Inc.") == "apple"

    def test_strip_llc(self) -> None:
        assert normalize_name("Goldman Sachs & Co. LLC") == "goldman sachs"

    def test_strip_the_prefix(self) -> None:
        assert normalize_name("The Goldman Sachs Group, Inc.") == "goldman sachs"

    def test_strip_ltd(self) -> None:
        assert normalize_name("HSBC Holdings Ltd.") == "hsbc"

    def test_strip_plc(self) -> None:
        assert normalize_name("Barclays PLC") == "barclays"

    def test_strip_corp(self) -> None:
        assert normalize_name("Microsoft Corp.") == "microsoft"

    def test_collapse_whitespace(self) -> None:
        assert normalize_name("  Goldman   Sachs  ") == "goldman sachs"

    def test_no_change_for_clean_name(self) -> None:
        assert normalize_name("Goldman Sachs") == "goldman sachs"

    def test_word_boundary_preserves_se_in_name(self) -> None:
        """'Mouse' ends with 'se' but that's not a legal suffix."""
        assert normalize_name("Mouse Corp.") == "mouse"

    def test_word_boundary_preserves_ag_in_name(self) -> None:
        assert normalize_name("Stalag") == "stalag"

    def test_word_boundary_strips_ag_as_suffix(self) -> None:
        assert normalize_name("Novartis AG") == "novartis"

    def test_word_boundary_preserves_nv_in_name(self) -> None:
        assert normalize_name("Envision") == "envision"


# ---------------------------------------------------------------------------
# ExactMatchStrategy tests
# ---------------------------------------------------------------------------

class TestExactMatchStrategy:
    """Tests for the exact match strategy."""

    def test_exact_canonical_name(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Goldman Sachs"))
        assert result is not None
        assert result.entity.id == 1
        assert result.strategy_used == "exact"
        assert result.confidence == 1.0

    def test_exact_alias(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="JP Morgan"))
        assert result is not None
        assert result.entity.id == 2

    def test_case_insensitive(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="TESLA"))
        assert result is not None
        assert result.entity.id == 5

    def test_with_legal_suffix(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Apple Inc."))
        assert result is not None
        assert result.entity.id == 3

    def test_normalised_alias_with_suffix(self, sample_entities: list[Entity]) -> None:
        """'The Goldman Sachs Group, Inc.' normalises to 'goldman sachs' → match."""
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(query_name="The Goldman Sachs Group, Inc.")
        )
        assert result is not None
        assert result.entity.id == 1

    def test_no_match(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Nonexistent Corp"))
        assert result is None

    def test_entity_type_filter(self, sample_entities: list[Entity]) -> None:
        strategy = ExactMatchStrategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(
                query_name="Goldman Sachs",
                entity_type_hint=EntityType.COUNTRY,
            )
        )
        assert result is None


# ---------------------------------------------------------------------------
# RulesMatchStrategy tests
# ---------------------------------------------------------------------------

class TestRulesMatchStrategy:
    """Tests for the rule-based match strategy."""

    def test_ticker_lookup(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="GS"))
        assert result is not None
        assert result.entity.id == 1
        assert result.strategy_used == "rules"

    def test_ticker_case_insensitive(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="aapl"))
        assert result is not None
        assert result.entity.id == 3

    def test_abbreviation_map(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="tsla"))
        assert result is not None
        assert result.entity.id == 5

    def test_fred_series_lookup(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="fed rate"))
        assert result is not None
        assert result.entity.id == 4
        assert "FRED" in result.match_details

    def test_fred_unemployment(self, sample_entities: list[Entity]) -> None:
        """FRED lookup for 'unemployment' requires UNRATE entity — returns None without it."""
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="unemployment"))
        # UNRATE entity doesn't exist in our fixture, so this should be None
        assert result is None

    def test_custom_abbreviation_map(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(
            sample_entities,
            abbreviation_map={"golden": "Goldman Sachs"},
        )
        result = strategy.resolve(ResolutionRequest(query_name="golden"))
        assert result is not None
        assert result.entity.id == 1

    def test_no_match(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="totally unknown"))
        assert result is None

    def test_entity_type_filter(self, sample_entities: list[Entity]) -> None:
        strategy = RulesMatchStrategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(
                query_name="GS",
                entity_type_hint=EntityType.COUNTRY,
            )
        )
        assert result is None


# ---------------------------------------------------------------------------
# FuzzyMatchStrategy tests
# ---------------------------------------------------------------------------

class TestFuzzyMatchStrategy:
    """Tests for the fuzzy match strategy."""

    def test_typo_match(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Goldmn Sachs"))
        assert result is not None
        assert result.entity.id == 1
        assert result.strategy_used == "fuzzy"

    def test_close_alias(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="JP Morgn"))
        assert result is not None
        assert result.entity.id == 2

    def test_partial_name(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Tesla Motors Inc"))
        assert result is not None
        assert result.entity.id == 5

    def test_reordered_tokens(self, sample_entities: list[Entity]) -> None:
        """token_sort_ratio should handle reordered words."""
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Sachs Goldman"))
        assert result is not None
        assert result.entity.id == 1

    def test_below_threshold_returns_none(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities, threshold=99.0)
        result = strategy.resolve(ResolutionRequest(query_name="Goldmn Sachs"))
        assert result is None

    def test_confidence_is_normalised(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Goldmn Sachs"))
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_entity_type_filter(self, sample_entities: list[Entity]) -> None:
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(
                query_name="Goldmn Sachs",
                entity_type_hint=EntityType.COUNTRY,
            )
        )
        assert result is None

    def test_goldmn_sachs_group_inc(self, sample_entities: list[Entity]) -> None:
        """The spec case: 'Goldmn Sachs Group Inc.' should fuzzy-match Goldman Sachs."""
        strategy = FuzzyMatchStrategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(query_name="Goldmn Sachs Group Inc.")
        )
        assert result is not None
        assert result.entity.id == 1


# ---------------------------------------------------------------------------
# SemanticMatchStrategy tests
# ---------------------------------------------------------------------------

class TestSemanticMatchStrategy:
    """Tests for the semantic match strategy (with mock embeddings)."""

    @staticmethod
    def _make_embedding(values: list[float]) -> list[float]:
        """Return a simple 3-d embedding for testing."""
        return values

    @staticmethod
    def _simple_embed(text: str) -> list[float]:
        """Deterministic mock embedding function.

        Maps known terms to fixed vectors so cosine similarity is predictable.
        """
        embeddings: dict[str, list[float]] = {
            "goldman sachs": [1.0, 0.0, 0.0],
            "investment bank": [0.95, 0.1, 0.0],
            "jpmorgan": [0.0, 1.0, 0.0],
            "apple": [0.0, 0.0, 1.0],
            "completely unrelated": [0.0, 0.0, 0.0],
            "banking giant": [0.9, 0.2, 0.0],
            "marginal finance": [0.6, 0.5, 0.5],
        }
        return embeddings.get(text.lower(), [0.33, 0.33, 0.33])

    def _build_strategy(
        self,
        entities: list[Entity],
        threshold: float = 0.82,
    ) -> SemanticMatchStrategy:
        embeddings = {
            1: [1.0, 0.0, 0.0],   # Goldman Sachs
            2: [0.0, 1.0, 0.0],   # JPMorgan
            3: [0.0, 0.0, 1.0],   # Apple
            5: [0.1, 0.0, 0.95],  # Tesla (near Apple in this toy space)
        }
        return SemanticMatchStrategy(
            entities,
            embeddings,
            embed_fn=self._simple_embed,
            threshold=threshold,
        )

    def test_high_similarity_match(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="Goldman Sachs"))
        assert result is not None
        assert result.entity.id == 1
        assert result.strategy_used == "semantic"

    def test_close_semantic_match(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="investment bank"))
        assert result is not None
        assert result.entity.id == 1
        assert result.confidence >= 0.82

    def test_no_match_below_threshold(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities, threshold=0.90)
        result = strategy.resolve(ResolutionRequest(query_name="marginal finance"))
        assert result is None

    def test_completely_unrelated(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(query_name="completely unrelated")
        )
        # Zero vector → zero cosine similarity with everything
        assert result is None

    def test_entity_type_filter(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities)
        result = strategy.resolve(
            ResolutionRequest(
                query_name="Goldman Sachs",
                entity_type_hint=EntityType.COUNTRY,
            )
        )
        assert result is None

    def test_confidence_range(self, sample_entities: list[Entity]) -> None:
        strategy = self._build_strategy(sample_entities)
        result = strategy.resolve(ResolutionRequest(query_name="banking giant"))
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# cosine_similarity unit tests
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    """Tests for the internal cosine similarity helper."""

    def test_identical_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# EntityResolver cascade tests
# ---------------------------------------------------------------------------

class TestEntityResolverCascade:
    """Tests for the full cascading resolver."""

    def _make_resolver(
        self,
        entities: list[Entity],
        with_semantic: bool = False,
    ) -> EntityResolver:
        embeddings: dict[int, list[float]] | None = None
        embed_fn = None
        if with_semantic:
            embeddings = {
                1: [1.0, 0.0, 0.0],
                2: [0.0, 1.0, 0.0],
                3: [0.0, 0.0, 1.0],
            }
            embed_fn = TestSemanticMatchStrategy._simple_embed
        return EntityResolver(
            entities,
            embeddings=embeddings,
            embed_fn=embed_fn,
        )

    def test_exact_match_wins(self, sample_entities: list[Entity]) -> None:
        """Exact match should be returned even when fuzzy would also match."""
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("Goldman Sachs")
        assert result is not None
        assert result.strategy_used == "exact"
        assert result.confidence == 1.0

    def test_rules_match_ticker(self, sample_entities: list[Entity]) -> None:
        """'GS' doesn't normalise-match but is a known ticker."""
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("GS")
        assert result is not None
        assert result.strategy_used == "rules"
        assert result.entity.canonical_name == "Goldman Sachs"

    def test_fuzzy_match_typo(self, sample_entities: list[Entity]) -> None:
        """'Goldmn Sachs Group Inc.' has a typo — fuzzy should catch it."""
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("Goldmn Sachs Group Inc.")
        assert result is not None
        assert result.strategy_used == "fuzzy"
        assert result.entity.id == 1

    def test_normalisation_plus_exact(self, sample_entities: list[Entity]) -> None:
        """'The Goldman Sachs & Co. LLC' normalises to 'goldman sachs' → exact."""
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("The Goldman Sachs & Co. LLC")
        assert result is not None
        assert result.strategy_used == "exact"
        assert result.entity.id == 1

    def test_semantic_fallback(self, sample_entities: list[Entity]) -> None:
        """When exact/rules/fuzzy all fail, semantic should be tried."""
        resolver = self._make_resolver(sample_entities, with_semantic=True)
        result = resolver.resolve("investment bank")
        assert result is not None
        assert result.strategy_used == "semantic"

    def test_no_match_returns_none(self, sample_entities: list[Entity]) -> None:
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("XYZ Unknown Entity 12345")
        assert result is None

    def test_entity_type_hint_filters(self, sample_entities: list[Entity]) -> None:
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("Goldman Sachs", entity_type_hint=EntityType.COUNTRY)
        assert result is None

    def test_cascade_order_exact_over_fuzzy(self, sample_entities: list[Entity]) -> None:
        """Exact match should take priority even when fuzzy has high confidence."""
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("Goldman Sachs Group")
        assert result is not None
        # "Goldman Sachs Group" is a registered alias → exact match, not fuzzy
        assert result.strategy_used == "exact"

    def test_fred_series_via_rules(self, sample_entities: list[Entity]) -> None:
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("fed rate")
        assert result is not None
        assert result.entity.canonical_name == "FEDFUNDS"
        assert result.strategy_used == "rules"

    def test_country_exact_match(self, sample_entities: list[Entity]) -> None:
        resolver = self._make_resolver(sample_entities)
        result = resolver.resolve("USA")
        assert result is not None
        assert result.entity.id == 6
        assert result.entity.entity_type == EntityType.COUNTRY

    def test_custom_fred_series_map_passthrough(self, sample_entities: list[Entity]) -> None:
        """fred_series_map injected at resolver level reaches RulesMatchStrategy."""
        resolver = EntityResolver(
            sample_entities,
            fred_series_map={"core pce": "PCEPILFE"},
        )
        # PCEPILFE entity doesn't exist in fixtures → None, but no AttributeError
        result = resolver.resolve("core pce")
        assert result is None  # entity missing, but map was accepted

    def test_without_semantic_still_works(self, sample_entities: list[Entity]) -> None:
        """Resolver should work fine when no embeddings are provided."""
        resolver = self._make_resolver(sample_entities, with_semantic=False)
        result = resolver.resolve("Goldman Sachs")
        assert result is not None
        assert result.strategy_used == "exact"
