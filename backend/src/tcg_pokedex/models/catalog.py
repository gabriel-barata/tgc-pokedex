from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Connection,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    Text,
    exists,
    select,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from tcg_pokedex.models.base import Base
from tcg_pokedex.views.sync import SOURCE

Row = dict[str, Any]
PROVENANCE = {"source", "fetched_at"}


class InvalidBatchError(Exception):
    """A set's write was rejected as a whole; none of it was stored."""


class Series(Base):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Set(Base):
    __tablename__ = "sets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    name: Mapped[str] = mapped_column(Text)
    release_date: Mapped[date] = mapped_column(Date)
    official_count: Mapped[int] = mapped_column(Integer)
    total_count: Mapped[int] = mapped_column(Integer)
    logo_url: Mapped[str | None] = mapped_column(Text)
    symbol_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("cardinality(variants) > 0", name="variants_not_empty"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    set_id: Mapped[str] = mapped_column(ForeignKey("sets.id"), index=True)
    collector_number: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    rarity: Mapped[str | None] = mapped_column(Text)
    illustrator: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    variants: Mapped[list[str]] = mapped_column(postgresql.ARRAY(Text))
    source: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


CATALOG_ORDER = (Set.release_date, Set.id)


def card_count(official: int, total: int) -> int:
    """The printed set size; sets with none printed (promos) count every card.

    Variants never count apart: the catalog holds one card per number.
    """
    return official or total


def set_exists(engine: Engine, set_id: str) -> bool:
    with engine.connect() as connection:
        return bool(connection.scalar(select(exists().where(Set.id == set_id))))


@dataclass(frozen=True)
class StoredSet:
    """What the catalog held for a set's series, set and cards before a write."""

    series: Row | None
    card_set: Row | None
    cards: dict[str, Row]


def save_set(
    engine: Engine,
    *,
    series_row: Row | None,
    set_row: Row,
    card_rows: list[Row],
    fetched_at: datetime,
) -> StoredSet:
    """Upsert a set, its cards and, when given, its series in one transaction.

    Returns what was stored before the write, without provenance columns. Every
    row written carries `fetched_at`.
    """
    provenance = {"source": SOURCE, "fetched_at": fetched_at}
    try:
        with engine.begin() as connection:
            stored = StoredSet(
                series=_stored(connection, Series, [series_row["id"]]).get(
                    series_row["id"]
                )
                if series_row
                else None,
                card_set=_stored(connection, Set, [set_row["id"]]).get(set_row["id"]),
                cards=_stored(connection, Card, [row["id"] for row in card_rows]),
            )
            if series_row:
                _upsert(connection, Series, [series_row], provenance)
            _upsert(connection, Set, [set_row], provenance)
            if card_rows:
                _upsert(connection, Card, card_rows, provenance)
    except IntegrityError as error:
        raise InvalidBatchError(str(error.orig)) from error
    return stored


def _stored(
    connection: Connection, table: type[Base], ids: list[str]
) -> dict[str, Row]:
    columns = [c for c in table.__table__.columns if c.name not in PROVENANCE]
    rows = connection.execute(
        select(*columns).where(table.__table__.c.id.in_(ids))
    ).mappings()
    return {row["id"]: dict(row) for row in rows}


def _upsert(
    connection: Connection, table: type[Base], rows: list[Row], provenance: Row
) -> None:
    """Insert rows, replacing every column of a row whose id already exists."""
    statement = postgresql.insert(table)
    columns = table.__table__.columns
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=[columns.id],
            set_={
                column.name: statement.excluded[column.name]
                for column in columns
                if not column.primary_key
            },
        ),
        [{**row, **provenance} for row in rows],
    )
