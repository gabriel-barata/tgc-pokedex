"""Contract every CatalogRepository must honour, run on the fake and the real one."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.domain import Fetched, SetBatch
from tcg_pokedex.catalog_sync.fakes import InMemoryCatalogRepository
from tcg_pokedex.catalog_sync.ports import CatalogRepository, InvalidBatchError
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.migrations import upgrade_to_head
from tests.catalog_sync.builders import make_card, make_series, make_set

FETCHED_AT = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
LATER = FETCHED_AT + timedelta(days=1)


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


SV01_BATCH = SetBatch(
    series=make_series(),
    card_set=make_set(),
    cards=(make_card(), make_card(id="sv01-002", name="Heracross")),
)


def test_saved_rows_are_loaded_back_with_their_fetch_time(
    repository: CatalogRepository,
) -> None:
    repository.save_set(SV01_BATCH, fetched_at=FETCHED_AT)

    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-002", "sv01-999"])

    assert stored.series == Fetched(make_series(), FETCHED_AT)
    assert stored.card_set == Fetched(make_set(), FETCHED_AT)
    assert stored.cards == {
        card.id: Fetched(card, FETCHED_AT) for card in SV01_BATCH.cards
    }


def test_save_set_replaces_rows_in_the_batch_and_keeps_the_others(
    repository: CatalogRepository,
) -> None:
    repository.save_set(SV01_BATCH, fetched_at=FETCHED_AT)
    renamed = make_card(name="Pineco Novo", rarity=None)

    repository.save_set(
        SetBatch(series=None, card_set=make_set(), cards=(renamed,)), fetched_at=LATER
    )

    stored = repository.load_stored("sv", "sv01", ["sv01-001", "sv01-002"])
    assert stored.series == Fetched(make_series(), FETCHED_AT)
    assert stored.cards == {
        "sv01-001": Fetched(renamed, LATER),
        "sv01-002": Fetched(SV01_BATCH.cards[1], FETCHED_AT),
    }


def test_save_set_is_all_or_nothing(repository: CatalogRepository) -> None:
    orphan = SetBatch(
        series=make_series(), card_set=make_set(series_id="xy"), cards=(make_card(),)
    )

    with pytest.raises(InvalidBatchError):
        repository.save_set(orphan, fetched_at=FETCHED_AT)

    stored = repository.load_stored("sv", "sv01", ["sv01-001"])
    assert (stored.series, stored.card_set, stored.cards) == (None, None, {})
