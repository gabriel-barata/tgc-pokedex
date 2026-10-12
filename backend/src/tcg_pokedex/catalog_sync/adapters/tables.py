from datetime import datetime

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
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from tcg_pokedex.database import metadata


def _provenance() -> tuple[Column[str], Column[datetime]]:
    return (
        Column("source", Text, nullable=False),
        Column("fetched_at", DateTime(timezone=True), nullable=False),
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
