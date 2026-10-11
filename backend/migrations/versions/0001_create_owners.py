"""Create owners and seed the household owner.

Revision ID: 0001
Revises:
Create Date: 2026-10-11 16:15:45.514353
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID, HOUSEHOLD_OWNER_NAME

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    owners = op.create_table(
        "owners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_owners")),
        sa.UniqueConstraint("name", name=op.f("uq_owners_name")),
    )
    op.bulk_insert(owners, [{"id": HOUSEHOLD_OWNER_ID, "name": HOUSEHOLD_OWNER_NAME}])


def downgrade() -> None:
    op.drop_table("owners")
