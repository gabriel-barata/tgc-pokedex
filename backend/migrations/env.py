"""Alembic environment.

The database URL comes from the migration runner (tcg_pokedex.migrations), or
from Settings when the alembic CLI is used directly.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from tcg_pokedex.config import Settings
from tcg_pokedex.schema import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

database_url: str = config.attributes.get("database_url") or str(
    Settings().database_url
)
engine = create_engine(database_url, poolclass=pool.NullPool)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
