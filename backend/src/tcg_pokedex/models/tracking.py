from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Engine, ForeignKey, Uuid, delete, exists, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base
from tcg_pokedex.models.catalog import CATALOG_ORDER, Card, Set
from tcg_pokedex.models.images import CardImage
from tcg_pokedex.views.sets import SetTracking


class TrackedSet(Base):
    __tablename__ = "tracked_sets"

    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("owners.id"), primary_key=True
    )
    set_id: Mapped[str] = mapped_column(
        ForeignKey("sets.id"), primary_key=True, index=True
    )
    tracked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def track_set(
    engine: Engine, owner_id: UUID, set_id: str, tracked_at: datetime
) -> bool:
    """Track the set for the owner; False when they already tracked it."""
    statement = (
        postgresql.insert(TrackedSet)
        .values(owner_id=owner_id, set_id=set_id, tracked_at=tracked_at)
        .on_conflict_do_nothing()
        .returning(TrackedSet.set_id)
    )
    with engine.begin() as connection:
        return connection.execute(statement).first() is not None


def untrack_set(engine: Engine, owner_id: UUID, set_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(TrackedSet).where(
                TrackedSet.owner_id == owner_id, TrackedSet.set_id == set_id
            )
        )


def tracked_set_ids(engine: Engine) -> list[str]:
    """Sets tracked by any owner, in catalog order."""
    statement = (
        select(Set.id)
        .where(exists().where(TrackedSet.set_id == Set.id))
        .order_by(*CATALOG_ORDER)
    )
    with engine.connect() as connection:
        return list(connection.scalars(statement))


def set_tracking(
    engine: Engine, owner_id: UUID, set_id: str, *, downloading: bool
) -> SetTracking:
    """The set's tracking state and image progress. The set must exist."""
    counts = (
        select(
            func.count(Card.id),
            func.count(CardImage.language),
            func.count(CardImage.card_id) - func.count(CardImage.language),
        )
        .select_from(Card)
        .outerjoin(CardImage)
        .where(Card.set_id == set_id)
    )
    tracked = select(
        exists().where(TrackedSet.owner_id == owner_id, TrackedSet.set_id == set_id)
    )
    with engine.connect() as connection:
        total, cached, unavailable = connection.execute(counts).one()
        is_tracked = bool(connection.scalar(tracked))
    return SetTracking(
        set_id=set_id,
        tracked=is_tracked,
        total_cards=total,
        cached=cached,
        unavailable=unavailable,
        downloading=downloading,
    )
