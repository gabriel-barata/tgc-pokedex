"""The whole database schema. Alembic compares migrations against this module."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from tcg_pokedex.db import metadata

HOUSEHOLD_OWNER_ID = UUID("9fb0c458-5ccf-477a-945e-276438b0f310")
"""The single owner every user-owned record belongs to in the MVP, seeded by the
first migration. Profiles (PTCG-031) replace it."""
HOUSEHOLD_OWNER_NAME = "Casa"


def _provenance() -> tuple[Column[str], Column[datetime]]:
    return (
        Column("source", Text, nullable=False),
        Column("fetched_at", DateTime(timezone=True), nullable=False),
    )


owners = Table(
    "owners",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)

series = Table(
    "series",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    *_provenance(),
)

sets = Table(
    "sets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("series_id", Text, ForeignKey("series.id"), nullable=False, index=True),
    Column("name", Text, nullable=False),
    Column("release_date", Date, nullable=False),
    Column("official_count", Integer, nullable=False),
    Column("total_count", Integer, nullable=False),
    Column("logo_url", Text, nullable=True),
    Column("symbol_url", Text, nullable=True),
    *_provenance(),
)

cards = Table(
    "cards",
    metadata,
    Column("id", Text, primary_key=True),
    Column("set_id", Text, ForeignKey("sets.id"), nullable=False, index=True),
    Column("collector_number", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("rarity", Text, nullable=True),
    Column("illustrator", Text, nullable=True),
    Column("image_url", Text, nullable=True),
    Column("variants", ARRAY(Text), nullable=False),
    *_provenance(),
    CheckConstraint("cardinality(variants) > 0", name="variants_not_empty"),
)

sync_runs = Table(
    "sync_runs",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("kind", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("duration_ms", Integer, nullable=True),
    Column("result", JSONB, nullable=True),
    Column("error", Text, nullable=True),
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
