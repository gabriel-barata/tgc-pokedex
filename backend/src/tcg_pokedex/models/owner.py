from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base

HOUSEHOLD_OWNER_ID = UUID("9fb0c458-5ccf-477a-945e-276438b0f310")
"""The single owner every user-owned record belongs to in the MVP, seeded by the
first migration. Profiles (PTCG-031) replace it."""
HOUSEHOLD_OWNER_NAME = "Casa"


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
