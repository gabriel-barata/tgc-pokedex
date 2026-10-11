from sqlalchemy import Column, DateTime, Table, Text, Uuid, func

from tcg_pokedex.database import metadata

owners = Table(
    "owners",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
)
