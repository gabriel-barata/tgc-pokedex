"""The whole database schema: every slice's tables on the shared metadata.

Alembic compares migrations against this, so each new table module is
imported here.
"""

from tcg_pokedex.catalog_sync.adapters.tables import cards, series, sets
from tcg_pokedex.database import metadata
from tcg_pokedex.image_cache.adapters.tables import (
    card_images,
    set_artwork,
    tracked_sets,
)
from tcg_pokedex.owners.adapters.tables import owners
from tcg_pokedex.sync_runs.adapters.tables import sync_runs

__all__ = [
    "card_images",
    "cards",
    "metadata",
    "owners",
    "series",
    "set_artwork",
    "sets",
    "sync_runs",
    "tracked_sets",
]
