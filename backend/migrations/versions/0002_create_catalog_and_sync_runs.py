"""Create the catalog tables (series, sets, cards) and sync_runs.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11 21:10:35.406384
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "series",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_series")),
    )
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_table(
        "sets",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("series_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("official_count", sa.Integer(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("symbol_url", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["series_id"], ["series.id"], name=op.f("fk_sets_series_id_series")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sets")),
    )
    op.create_index(op.f("ix_sets_series_id"), "sets", ["series_id"], unique=False)
    op.create_table(
        "cards",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("set_id", sa.Text(), nullable=False),
        sa.Column("collector_number", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("rarity", sa.Text(), nullable=True),
        sa.Column("illustrator", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("variants", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "cardinality(variants) > 0", name=op.f("ck_cards_variants_not_empty")
        ),
        sa.ForeignKeyConstraint(
            ["set_id"], ["sets.id"], name=op.f("fk_cards_set_id_sets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cards")),
    )
    op.create_index(op.f("ix_cards_set_id"), "cards", ["set_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cards_set_id"), table_name="cards")
    op.drop_table("cards")
    op.drop_index(op.f("ix_sets_series_id"), table_name="sets")
    op.drop_table("sets")
    op.drop_table("sync_runs")
    op.drop_table("series")
