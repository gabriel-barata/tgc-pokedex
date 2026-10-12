"""Imports every table class, so Atlas's SQLAlchemy loader sees the whole schema."""

from tcg_pokedex.models import catalog, images, owner, ownership, sync_runs, tracking
from tcg_pokedex.models.base import Base

__all__ = [
    "Base",
    "catalog",
    "images",
    "owner",
    "ownership",
    "sync_runs",
    "tracking",
]
