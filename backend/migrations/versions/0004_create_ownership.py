"""Create ownership.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12 16:53:35.293756
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ownership",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity BETWEEN 0 AND 999", name=op.f("ck_ownership_quantity_in_range")
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name=op.f("fk_ownership_card_id_cards")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["owners.id"], name=op.f("fk_ownership_owner_id_owners")
        ),
        sa.PrimaryKeyConstraint(
            "owner_id", "card_id", "variant", name=op.f("pk_ownership")
        ),
    )


def downgrade() -> None:
    op.drop_table("ownership")
