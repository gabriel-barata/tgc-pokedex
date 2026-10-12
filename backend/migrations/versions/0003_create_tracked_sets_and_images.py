"""Create tracked_sets, card_images and set_artwork.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12 12:40:18.475220
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "set_artwork",
        sa.Column("set_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('logo', 'symbol')", name=op.f("ck_set_artwork_kind_known")
        ),
        sa.ForeignKeyConstraint(
            ["set_id"], ["sets.id"], name=op.f("fk_set_artwork_set_id_sets")
        ),
        sa.PrimaryKeyConstraint("set_id", "kind", name=op.f("pk_set_artwork")),
    )
    op.create_table(
        "tracked_sets",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("set_id", sa.Text(), nullable=False),
        sa.Column("tracked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_tracked_sets_owner_id_owners")
        ),
        sa.ForeignKeyConstraint(
            ["set_id"], ["sets.id"], name=op.f("fk_tracked_sets_set_id_sets")
        ),
        sa.PrimaryKeyConstraint("owner_id", "set_id", name=op.f("pk_tracked_sets")),
    )
    op.create_index(
        op.f("ix_tracked_sets_set_id"), "tracked_sets", ["set_id"], unique=False
    )
    op.create_table(
        "card_images",
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "language IN ('pt', 'en')", name=op.f("ck_card_images_language_known")
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name=op.f("fk_card_images_card_id_cards")
        ),
        sa.PrimaryKeyConstraint("card_id", name=op.f("pk_card_images")),
    )


def downgrade() -> None:
    op.drop_table("card_images")
    op.drop_index(op.f("ix_tracked_sets_set_id"), table_name="tracked_sets")
    op.drop_table("tracked_sets")
    op.drop_table("set_artwork")
