from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Engine

from tcg_pokedex.database import get_engine
from tcg_pokedex.models.owner import HOUSEHOLD_OWNER_ID


def get_owner_id() -> UUID:
    """The owner the API acts as. Profiles (PTCG-031) replace only this."""
    return HOUSEHOLD_OWNER_ID


Owner = Annotated[UUID, Depends(get_owner_id)]
Database = Annotated[Engine, Depends(get_engine)]
