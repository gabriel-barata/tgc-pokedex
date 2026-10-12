"""Contract every ImageCacheRepository must honour, run on the fake and the real one.

Both hold the same catalog: sv01 (two cards, logo and symbol) and sv02, released
later (one card, a logo and no symbol).
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import insert

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.domain import SetBatch
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.image_cache.adapters.postgres import PostgresImageCacheRepository
from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    ArtworkToFetch,
    CardToResolve,
    Language,
    SetTracking,
    StoredCardImage,
)
from tcg_pokedex.image_cache.fakes import InMemoryImageCacheRepository
from tcg_pokedex.image_cache.ports import ImageCacheRepository
from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.owners.adapters.tables import owners
from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID
from tests.catalog_sync.builders import make_card, make_series, make_set

AT = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
LATER = AT + timedelta(days=1)
OTHER_OWNER_ID = UUID("00000000-0000-4000-8000-000000000002")

SV01 = make_set()
SV02 = make_set(
    id="sv02",
    release_date=SV01.release_date + timedelta(days=70),
    logo_url="https://assets.tcgdex.net/pt/sv/sv02/logo",
    symbol_url=None,
)
SV01_001 = make_card()
SV01_002 = make_card(id="sv01-002", image_url=None)
SV02_001 = make_card(
    id="sv02-001", set_id="sv02", image_url="https://assets.tcgdex.net/pt/sv/sv02/001"
)


def make_fake_repository(_request: pytest.FixtureRequest) -> ImageCacheRepository:
    repository = InMemoryImageCacheRepository()
    for card_set in (SV01, SV02):
        repository.add_set(card_set.id, card_set.logo_url, card_set.symbol_url)
    for card in (SV01_001, SV01_002, SV02_001):
        repository.add_card(card.id, card.set_id, card.image_url)
    return repository


def make_postgres_repository(request: pytest.FixtureRequest) -> ImageCacheRepository:
    database_url: str = request.getfixturevalue("empty_database_url")
    upgrade_to_head(database_url)
    engine = create_database_engine(database_url)
    request.addfinalizer(engine.dispose)
    catalog = PostgresCatalogRepository(engine)
    catalog.save_set(
        SetBatch(series=make_series(), card_set=SV01, cards=(SV01_001, SV01_002)), AT
    )
    catalog.save_set(SetBatch(series=None, card_set=SV02, cards=(SV02_001,)), AT)
    with engine.begin() as connection:
        connection.execute(insert(owners).values(id=OTHER_OWNER_ID, name="Outra"))
    return PostgresImageCacheRepository(engine)


@pytest.fixture(
    params=[make_fake_repository, make_postgres_repository], ids=["fake", "postgres"]
)
def repository(request: pytest.FixtureRequest) -> ImageCacheRepository:
    factory: Callable[[pytest.FixtureRequest], ImageCacheRepository] = request.param
    return factory(request)


def test_set_exists_only_for_catalog_sets(repository: ImageCacheRepository) -> None:
    assert repository.set_exists("sv01")
    assert not repository.set_exists("xy1")


def test_tracking_is_per_owner_and_idempotent(
    repository: ImageCacheRepository,
) -> None:
    assert repository.track(HOUSEHOLD_OWNER_ID, "sv01", AT) is True
    assert repository.track(HOUSEHOLD_OWNER_ID, "sv01", AT) is False
    repository.track(HOUSEHOLD_OWNER_ID, "sv02", AT)
    repository.track(OTHER_OWNER_ID, "sv02", AT)
    assert repository.tracked_set_ids() == ["sv01", "sv02"]

    repository.untrack(HOUSEHOLD_OWNER_ID, "sv02")
    repository.untrack(HOUSEHOLD_OWNER_ID, "sv02")

    assert repository.progress(HOUSEHOLD_OWNER_ID, "sv01").tracked
    assert not repository.progress(HOUSEHOLD_OWNER_ID, "sv02").tracked
    assert repository.progress(OTHER_OWNER_ID, "sv02").tracked
    assert not repository.progress(OTHER_OWNER_ID, "sv01").tracked
    assert repository.tracked_set_ids() == ["sv01", "sv02"]


def test_card_image_rows_are_upserted_and_counted(
    repository: ImageCacheRepository,
) -> None:
    repository.save_card_images([("sv01-001", Language.EN), ("sv01-002", None)], AT)
    repository.save_card_images([("sv01-001", Language.PT)], LATER)

    assert repository.cards_to_resolve("sv01") == [
        CardToResolve(
            card_id="sv01-001",
            pt_image_url=SV01_001.image_url,
            stored=StoredCardImage(language=Language.PT, fetched_at=LATER),
        ),
        CardToResolve(
            card_id="sv01-002",
            pt_image_url=None,
            stored=StoredCardImage(language=None, fetched_at=AT),
        ),
    ]
    assert repository.cards_to_resolve("sv02") == [
        CardToResolve(card_id="sv02-001", pt_image_url=SV02_001.image_url, stored=None)
    ]
    assert repository.progress(HOUSEHOLD_OWNER_ID, "sv01") == SetTracking(
        set_id="sv01",
        tracked=False,
        total_cards=2,
        cached=1,
        unavailable=1,
        downloading=False,
    )


def test_artwork_lists_every_set_with_its_cached_flag(
    repository: ImageCacheRepository,
) -> None:
    repository.save_artwork("sv01", ArtworkKind.LOGO, AT)
    repository.save_artwork("sv01", ArtworkKind.LOGO, LATER)

    assert repository.artwork_to_fetch() == [
        ArtworkToFetch("sv01", ArtworkKind.LOGO, SV01.logo_url, cached=True),
        ArtworkToFetch("sv01", ArtworkKind.SYMBOL, SV01.symbol_url, cached=False),
        ArtworkToFetch("sv02", ArtworkKind.LOGO, SV02.logo_url, cached=False),
        ArtworkToFetch("sv02", ArtworkKind.SYMBOL, None, cached=False),
    ]
