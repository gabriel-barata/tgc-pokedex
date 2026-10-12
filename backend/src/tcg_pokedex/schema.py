"""The whole database schema: every slice's tables on the shared metadata.

Alembic compares migrations against this, so each new table module is
imported here.
"""

from tcg_pokedex.catalog_sync.adapters.tables import cards, series, sets, sync_runs
from tcg_pokedex.database import metadata
from tcg_pokedex.owners.adapters.tables import owners

__all__ = ["cards", "metadata", "owners", "series", "sets", "sync_runs"]
