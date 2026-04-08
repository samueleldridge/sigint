"""Semantic embedding matching strategy using sentence-transformers and cosine similarity."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from sigint.entity_resolution.models import Entity, MatchResult, ResolutionRequest

DEFAULT_SEMANTIC_THRESHOLD: float = 0.82


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _default_embed(text: str) -> list[float]:
    """Embed text using sentence-transformers (lazy-loaded)."""
    model = _get_model()
    embedding: list[float] = model.encode(text).tolist()
    return embedding


_model: Any = None


def _get_model() -> Any:
    """Lazy-load the sentence-transformers model."""
    global _model  # noqa: PLW0603
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for semantic matching. "
                "Install with: pip install sigint[semantic]"
            ) from exc
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


class SemanticMatchStrategy:
    """Match query by embedding cosine similarity against pre-computed entity embeddings.

    This is an in-memory stopgap. The target architecture (see docs/architecture.md)
    uses pgvector for similarity search, which avoids loading all embeddings into RAM
    and scales to large entity corpora. This implementation should be replaced with a
    pgvector-backed strategy once the data layer is populated.
    """

    def __init__(
        self,
        entities: list[Entity],
        embeddings: dict[int, list[float]],
        embed_fn: Callable[[str], list[float]] | None = None,
        threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
    ) -> None:
        self._entities = {e.id: e for e in entities}
        self._embeddings = embeddings
        self._embed_fn = embed_fn or _default_embed
        self._threshold = threshold

    def resolve(self, request: ResolutionRequest) -> MatchResult | None:
        """Embed the query and find the closest entity above the threshold."""
        query_embedding = self._embed_fn(request.query_name)

        # TODO: replace in-memory loop with pgvector nearest-neighbour query
        # once the data layer is wired up (see docs/architecture.md).
        best_score: float = 0.0
        best_entity: Entity | None = None

        for entity_id, entity_embedding in self._embeddings.items():
            entity = self._entities.get(entity_id)
            if entity is None:
                continue
            if (
                request.entity_type_hint is not None
                and entity.entity_type != request.entity_type_hint
            ):
                continue

            score = _cosine_similarity(query_embedding, entity_embedding)
            if score > best_score:
                best_score = score
                best_entity = entity

        if best_entity is not None and best_score >= self._threshold:
            return MatchResult(
                entity=best_entity,
                strategy_used="semantic",
                confidence=round(best_score, 4),
                match_details=(
                    f"Semantic match '{request.query_name}' → "
                    f"'{best_entity.canonical_name}' (similarity={best_score:.4f})"
                ),
            )

        return None
