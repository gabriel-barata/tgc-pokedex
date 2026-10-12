from sqlalchemy import Column, DateTime, Integer, Table, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from tcg_pokedex.database import metadata

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
