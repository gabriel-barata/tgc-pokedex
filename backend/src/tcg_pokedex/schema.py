"""The whole database schema: every slice's tables on the shared metadata.

Alembic compares migrations against this, so each new table module is
imported here.
"""

from tcg_pokedex.database import metadata
from tcg_pokedex.owners.adapters.tables import owners

__all__ = ["metadata", "owners"]
