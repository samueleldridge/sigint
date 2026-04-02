"""initial schema: entity_canonical and entity_aliases

Revision ID: 2a543b18955c
Revises:
Create Date: 2026-04-02 00:59:30.272038

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a543b18955c"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create entity_canonical and entity_aliases tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "entity_canonical",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("lei", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),  # vector(384) added via raw SQL
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    # Replace the text column with a proper vector column
    op.execute("ALTER TABLE entity_canonical DROP COLUMN embedding")
    op.execute("ALTER TABLE entity_canonical ADD COLUMN embedding vector(384)")

    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "canonical_id",
            sa.Integer,
            sa.ForeignKey("entity_canonical.id"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.Text, nullable=False),
        sa.Column("alias_type", sa.String(50), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "alias_name", "canonical_id", name="uq_alias_name_canonical_id"
        ),
    )

    op.create_index("ix_entity_aliases_alias_name", "entity_aliases", ["alias_name"])
    op.execute(
        "CREATE INDEX ix_entity_canonical_embedding ON entity_canonical "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    """Drop entity_aliases and entity_canonical tables."""
    op.execute("DROP INDEX IF EXISTS ix_entity_canonical_embedding")
    op.drop_index("ix_entity_aliases_alias_name", table_name="entity_aliases")
    op.drop_table("entity_aliases")
    op.drop_table("entity_canonical")
