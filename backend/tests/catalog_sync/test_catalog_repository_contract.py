"""Contract every CatalogRepository must honour, run on the fake and the real one."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.domain import (
    CardCounts,
    Failure,
    Fetched,
    KindCounts,
    RunStatus,
    SetBatch,
    SetCounts,
    SyncCounts,
    SyncKind,
    SyncResult,
    SyncRun,
    Variant,
)
from tcg_pokedex.catalog_sync.fakes import InMemoryCatalogRepository
from tcg_pokedex.catalog_sync.ports import CatalogRepository, InvalidBatchError
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tests.catalog_sync.builders import make_card, make_series, make_set

FETCHED_AT = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)


def make_fake_repository(_request: pytest.FixtureRequest) -> CatalogRepository:
    return InMemoryCatalogRepository()


def make_postgres_repository(request: pytest.FixtureRequest) -> CatalogRepository:
    database_url: str = request.getfixturevalue("empty_database_url")
    upgrade_to_head(database_url)
    engine = create_database_engine(database_url)
    request.addfinalizer(engine.dispose)
    return PostgresCatalogRepository(engine)


@pytest.fixture(
    params=[make_fake_repository, make_postgres_repository], ids=["fake", "postgres"]
)
def repository(request: pytest.FixtureRequest) -> CatalogRepository:
    factory: Callable[[pytest.FixtureRequest], CatalogRepository] = request.param
    return factory(request)


def sv01_batch() -> SetBatch:
    return SetBatch(
        series=make_series(),
        card_set=make_set(),
        cards=(
            make_card(),
            make_card(id="sv01-002", collector_number="002", name="Heracross"),
        ),
    )


def open_run() -> SyncRun:
    return SyncRun(
        id=uuid4(),
        kind=SyncKind.CATALOG,
        status=RunStatus.RUNNING,
        started_at=FETCHED_AT,
    )


def test_load_stored_on_an_empty_store_finds_nothing(
    repository: CatalogRepository,
) -> None:
    stored = repository.load_stored("sv", "sv01", ["sv01-001"])

    assert stored.series is None
    assert stored.card_set is None
    assert stored.cards == {}


def test_saved_rows_are_loaded_back_with_their_fetch_time(
    repository: CatalogRepository,
) -> None:
    batch = sv01_batch()

    repository.save_set(batch, fetched_at=FETCHED_AT)
    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-002"])

    assert stored.series == Fetched(make_series(), FETCHED_AT)
    assert stored.card_set == Fetched(make_set(), FETCHED_AT)
    assert stored.cards == {card.id: Fetched(card, FETCHED_AT) for card in batch.cards}


def test_load_stored_omits_cards_that_are_not_stored(
    repository: CatalogRepository,
) -> None:
    repository.save_set(sv01_batch(), fetched_at=FETCHED_AT)

    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-999"])

    assert set(stored.cards) == {"sv01-001"}


def test_a_batch_without_a_series_uses_the_stored_one(
    repository: CatalogRepository,
) -> None:
    repository.save_set(sv01_batch(), fetched_at=FETCHED_AT)
    later = FETCHED_AT + timedelta(minutes=1)
    batch = SetBatch(
        series=None,
        card_set=make_set(id="sv02", name="Evoluções em Paldea"),
        cards=(make_card(id="sv02-001", set_id="sv02"),),
    )

    repository.save_set(batch, fetched_at=later)
    stored = repository.load_stored("sv", "sv02", ["sv02-001"])

    assert stored.series == Fetched(make_series(), FETCHED_AT)
    assert stored.card_set == Fetched(batch.card_set, later)
    assert stored.cards == {"sv02-001": Fetched(batch.cards[0], later)}


@pytest.mark.parametrize(
    "variants",
    [
        frozenset(Variant),
        frozenset({Variant.HOLO}),
        frozenset({Variant.W_PROMO, Variant.NORMAL}),
    ],
    ids=["all", "holo", "unordered"],
)
def test_variants_round_trip(
    repository: CatalogRepository, variants: frozenset[Variant]
) -> None:
    card = make_card(variants=variants)

    repository.save_set(
        SetBatch(series=make_series(), card_set=make_set(), cards=(card,)),
        fetched_at=FETCHED_AT,
    )

    stored = repository.load_stored("sv", "sv01", [card.id])
    assert stored.cards[card.id].value.variants == variants


def test_save_set_is_all_or_nothing(repository: CatalogRepository) -> None:
    orphan = SetBatch(
        series=make_series(),
        card_set=make_set(series_id="xy"),
        cards=(make_card(),),
    )

    with pytest.raises(InvalidBatchError):
        repository.save_set(orphan, fetched_at=FETCHED_AT)

    stored = repository.load_stored("sv", "sv01", ["sv01-001"])
    assert stored.series is None
    assert stored.card_set is None
    assert stored.cards == {}


def test_get_run_returns_the_started_run(repository: CatalogRepository) -> None:
    run = open_run()

    repository.start_run(run)

    assert repository.get_run(run.id) == run


def test_get_run_returns_the_finished_run(repository: CatalogRepository) -> None:
    run = open_run()
    closed = run.model_copy(
        update={
            "status": RunStatus.PARTIAL,
            "finished_at": FETCHED_AT + timedelta(seconds=2),
            "duration_ms": 2000,
            "result": SyncResult(
                counts=SyncCounts(
                    series=KindCounts(fetched=1, created=1, updated=0, unchanged=0),
                    sets=SetCounts(
                        fetched=1,
                        created=0,
                        updated=1,
                        unchanged=0,
                        skipped=1,
                        failed=0,
                    ),
                    cards=CardCounts(
                        fetched=2, created=1, updated=0, unchanged=1, failed=1
                    ),
                ),
                failures=(
                    Failure(kind="card", provider_id="sv01-003", reason="HTTP 404"),
                ),
            ),
        }
    )
    repository.start_run(run)

    repository.finish_run(closed)

    assert repository.get_run(run.id) == closed


def test_get_run_returns_the_error_of_a_failed_run(
    repository: CatalogRepository,
) -> None:
    run = open_run()
    closed = run.model_copy(
        update={
            "status": RunStatus.FAILED,
            "finished_at": FETCHED_AT,
            "duration_ms": 0,
            "error": "HTTP 500 after 3 attempts",
        }
    )
    repository.start_run(run)

    repository.finish_run(closed)

    assert repository.get_run(run.id) == closed


def test_get_run_of_an_unknown_id_is_none(repository: CatalogRepository) -> None:
    assert repository.get_run(uuid4()) is None


def test_save_set_leaves_rows_outside_the_batch_untouched(
    repository: CatalogRepository,
) -> None:
    repository.save_set(sv01_batch(), fetched_at=FETCHED_AT)
    later = FETCHED_AT + timedelta(days=1)
    sv02 = SetBatch(
        series=make_series(),
        card_set=make_set(id="sv02", name="Evoluções em Paldea"),
        cards=(make_card(id="sv02-001", set_id="sv02", name="Sprigatito"),),
    )
    only_first_card = SetBatch(
        series=None, card_set=make_set(), cards=(make_card(name="Pineco Novo"),)
    )

    repository.save_set(sv02, fetched_at=later)
    repository.save_set(only_first_card, fetched_at=later)

    untouched = make_card(id="sv01-002", collector_number="002", name="Heracross")
    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-002"])
    assert stored.cards["sv01-002"] == Fetched(untouched, FETCHED_AT)
    assert stored.cards["sv01-001"] == Fetched(make_card(name="Pineco Novo"), later)


def test_save_set_replaces_every_attribute_of_existing_rows(
    repository: CatalogRepository,
) -> None:
    repository.save_set(
        SetBatch(
            series=make_series(),
            card_set=make_set(),
            cards=(make_card(variants=[Variant.NORMAL]),),
        ),
        fetched_at=FETCHED_AT,
    )
    later = FETCHED_AT + timedelta(days=1)
    changed = SetBatch(
        series=make_series(name="Scarlet & Violet"),
        card_set=make_set(
            name="Scarlet & Violet",
            official_count=200,
            total_count=260,
            logo_url=None,
            symbol_url="https://assets.tcgdex.net/univ/sv/sv01/symbol-2",
        ),
        cards=(
            make_card(
                collector_number="001a",
                name="Pineco Novo",
                rarity=None,
                illustrator="Outro",
                image_url=None,
                variants=[Variant.NORMAL, Variant.REVERSE],
            ),
        ),
    )

    repository.save_set(changed, fetched_at=later)

    stored = repository.load_stored("sv", "sv01", ["sv01-001"])
    assert changed.series is not None
    assert stored.series == Fetched(changed.series, later)
    assert stored.card_set == Fetched(changed.card_set, later)
    assert stored.cards == {"sv01-001": Fetched(changed.cards[0], later)}


def test_saving_the_same_batch_again_only_moves_the_fetch_time(
    repository: CatalogRepository,
) -> None:
    batch = sv01_batch()
    later = FETCHED_AT + timedelta(hours=1)

    repository.save_set(batch, fetched_at=FETCHED_AT)
    repository.save_set(batch, fetched_at=later)

    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-002"])
    assert stored.series == Fetched(make_series(), later)
    assert stored.card_set == Fetched(make_set(), later)
    assert stored.cards == {card.id: Fetched(card, later) for card in batch.cards}
