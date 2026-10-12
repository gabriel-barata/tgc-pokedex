from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Table,
    Text,
    Uuid,
)

from tcg_pokedex.database import metadata


def _provenance() -> tuple[Column[str], Column[datetime]]:
    return (
        Column("source", Text, nullable=False),
        Column("fetched_at", DateTime(timezone=True), nullable=False),
    )


tracked_sets = Table(
    "tracked_sets",
    metadata,
    Column("owner_id", Uuid(as_uuid=True), ForeignKey("owners.id"), primary_key=True),
    Column("set_id", Text, ForeignKey("sets.id"), primary_key=True, index=True),
    Column("tracked_at", DateTime(timezone=True), nullable=False),
)

card_images = Table(
    "card_images",
    metadata,
    Column("card_id", Text, ForeignKey("cards.id"), primary_key=True),
    Column("language", Text, nullable=True),
    *_provenance(),
    CheckConstraint("language IN ('pt', 'en')", name="language_known"),
)

set_artwork = Table(
    "set_artwork",
    metadata,
    Column("set_id", Text, ForeignKey("sets.id"), primary_key=True),
    Column("kind", Text, primary_key=True),
    *_provenance(),
    CheckConstraint("kind IN ('logo', 'symbol')", name="kind_known"),
)
