from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, RowMapping, Table, insert, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from tcg_pokedex.catalog_sync.adapters import tables
from tcg_pokedex.catalog_sync.domain import (
    SOURCE,
    Card,
    CardSet,
    Fetched,
    Series,
    SetBatch,
    StoredCatalog,
    SyncRun,
    Variant,
)
from tcg_pokedex.catalog_sync.ports import InvalidBatchError


class PostgresCatalogRepository:
    """CatalogRepository on Postgres.

    Each `save_set` is one transaction that upserts by provider id and never deletes.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def start_run(self, run: SyncRun) -> None:
        with self._engine.begin() as connection:
            connection.execute(insert(tables.sync_runs).values(_run_row(run)))

    def finish_run(self, run: SyncRun) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(tables.sync_runs)
                .where(tables.sync_runs.c.id == run.id)
                .values(_run_row(run))
            )

    def get_run(self, run_id: UUID) -> SyncRun | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    select(tables.sync_runs).where(tables.sync_runs.c.id == run_id)
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else SyncRun.model_validate(dict(row))

    def load_stored(
        self, series_id: str, set_id: str, card_ids: Sequence[str]
    ) -> StoredCatalog:
        with self._engine.connect() as connection:
            series_row = (
                connection.execute(
                    select(tables.series).where(tables.series.c.id == series_id)
                )
                .mappings()
                .one_or_none()
            )
            set_row = (
                connection.execute(
                    select(tables.sets).where(tables.sets.c.id == set_id)
                )
                .mappings()
                .one_or_none()
            )
            card_rows = (
                connection.execute(
                    select(tables.cards).where(tables.cards.c.id.in_(card_ids))
                )
                .mappings()
                .all()
            )
        return StoredCatalog(
            series=None if series_row is None else _stored_series(series_row),
            card_set=None if set_row is None else _stored_set(set_row),
            cards={row["id"]: _stored_card(row) for row in card_rows},
        )

    def save_set(self, batch: SetBatch, fetched_at: datetime) -> None:
        try:
            with self._engine.begin() as connection:
                if batch.series is not None:
                    _upsert(
                        connection,
                        tables.series,
                        [_series_row(batch.series, fetched_at)],
                    )
                _upsert(connection, tables.sets, [_set_row(batch.card_set, fetched_at)])
                if batch.cards:
                    _upsert(
                        connection,
                        tables.cards,
                        [_card_row(card, fetched_at) for card in batch.cards],
                    )
        except IntegrityError as error:
            raise InvalidBatchError(str(error.orig)) from error


def _upsert(connection: Connection, table: Table, rows: list[dict[str, Any]]) -> None:
    """Insert rows, replacing every column of a row whose id already exists."""
    statement = postgresql.insert(table)
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=[table.c.id],
            set_={
                column.name: statement.excluded[column.name]
                for column in table.columns
                if not column.primary_key
            },
        ),
        rows,
    )


def _run_row(run: SyncRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "kind": run.kind.value,
        "source": run.source,
        "status": run.status.value,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "result": None if run.result is None else run.result.model_dump(mode="json"),
        "error": run.error,
    }


def _provenance(fetched_at: datetime) -> dict[str, Any]:
    return {"source": SOURCE, "fetched_at": fetched_at}


def _series_row(series: Series, fetched_at: datetime) -> dict[str, Any]:
    return {"id": series.id, "name": series.name, **_provenance(fetched_at)}


def _set_row(card_set: CardSet, fetched_at: datetime) -> dict[str, Any]:
    return {
        "id": card_set.id,
        "series_id": card_set.series_id,
        "name": card_set.name,
        "release_date": card_set.release_date,
        "official_count": card_set.official_count,
        "total_count": card_set.total_count,
        "logo_url": card_set.logo_url,
        "symbol_url": card_set.symbol_url,
        **_provenance(fetched_at),
    }


def _card_row(card: Card, fetched_at: datetime) -> dict[str, Any]:
    return {
        "id": card.id,
        "set_id": card.set_id,
        "collector_number": card.collector_number,
        "name": card.name,
        "rarity": card.rarity,
        "illustrator": card.illustrator,
        "image_url": card.image_url,
        "variants": [variant.value for variant in Variant if variant in card.variants],
        **_provenance(fetched_at),
    }


def _stored_series(row: RowMapping) -> Fetched[Series]:
    return Fetched(Series(id=row["id"], name=row["name"]), row["fetched_at"])


def _stored_set(row: RowMapping) -> Fetched[CardSet]:
    return Fetched(
        CardSet(
            id=row["id"],
            series_id=row["series_id"],
            name=row["name"],
            release_date=row["release_date"],
            official_count=row["official_count"],
            total_count=row["total_count"],
            logo_url=row["logo_url"],
            symbol_url=row["symbol_url"],
        ),
        row["fetched_at"],
    )


def _stored_card(row: RowMapping) -> Fetched[Card]:
    return Fetched(
        Card(
            id=row["id"],
            set_id=row["set_id"],
            collector_number=row["collector_number"],
            name=row["name"],
            rarity=row["rarity"],
            illustrator=row["illustrator"],
            image_url=row["image_url"],
            variants=frozenset(Variant(value) for value in row["variants"]),
        ),
        row["fetched_at"],
    )
