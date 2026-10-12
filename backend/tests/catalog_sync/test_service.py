import logging
from datetime import UTC, datetime, timedelta

import pytest

from tcg_pokedex.catalog_sync.domain import (
    CardCounts,
    Failure,
    Fetched,
    KindCounts,
    SetBatch,
    SetCounts,
    SyncResult,
)
from tcg_pokedex.catalog_sync.fakes import (
    InMemoryCatalogProvider,
    InMemoryCatalogRepository,
)
from tcg_pokedex.catalog_sync.service import sync_catalog
from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.sync_runs.domain import RunStatus
from tcg_pokedex.sync_runs.fakes import InMemorySyncRunRepository
from tests.catalog_sync.builders import make_card, make_listing, make_series, make_set

START = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
LATER = START + timedelta(hours=1)

SV = make_series()
SV01 = make_set()
SV02 = make_set(id="sv02", name="Evoluções em Paldea")
SV01_CARDS = (make_card(), make_card(id="sv01-002", name="Heracross"))
SV02_CARDS = (make_card(id="sv02-001", set_id="sv02", name="Sprigatito"),)


def catalog() -> InMemoryCatalogProvider:
    """sv (sv01, sv02), the empty base1 and the Pocket series tcgp (A1)."""
    provider = InMemoryCatalogProvider()
    provider.add_set(
        make_listing(
            card_set=make_set(id="base1", series_id="base"),
            series=make_series(id="base"),
        )
    )
    provider.add_set(
        make_listing(card_ids=[card.id for card in SV01_CARDS]), SV01_CARDS
    )
    provider.add_set(make_listing(card_set=SV02, card_ids=["sv02-001"]), SV02_CARDS)
    provider.add_set(
        make_listing(
            card_set=make_set(id="A1", series_id="tcgp"),
            series=make_series(id="tcgp"),
            card_ids=["A1-001"],
        ),
        [make_card(id="A1-001", set_id="A1")],
    )
    return provider


def test_a_first_run_stores_every_physical_set_with_cards() -> None:
    provider = catalog()
    repository = InMemoryCatalogRepository()
    runs = InMemorySyncRunRepository()

    run = sync_catalog(provider, repository, runs, FakeClock(START))

    assert repository.series == {"sv": Fetched(SV, START)}
    assert repository.sets == {
        "sv01": Fetched(SV01, START),
        "sv02": Fetched(SV02, START),
    }
    assert repository.cards == {
        card.id: Fetched(card, START) for card in SV01_CARDS + SV02_CARDS
    }
    assert not [path for path in provider.requests if "tcgp" in path]
    assert run.status is RunStatus.SUCCEEDED
    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=1, created=1, updated=0, unchanged=0
    )
    assert run.result.counts.sets == SetCounts(
        fetched=2, created=2, updated=0, unchanged=0, skipped=1, failed=0
    )
    assert runs.get_run(run.id, SyncResult) == run


def test_a_second_run_updates_changed_rows_and_keeps_unlisted_ones() -> None:
    repository = InMemoryCatalogRepository()
    runs = InMemorySyncRunRepository()
    sync_catalog(catalog(), repository, runs, FakeClock(START))
    renamed = make_card(name="Pineco Renomeado")
    provider = InMemoryCatalogProvider()
    provider.add_set(make_listing(card_ids=["sv01-001"]), [renamed])

    run = sync_catalog(provider, repository, runs, FakeClock(LATER))

    assert repository.cards["sv01-001"] == Fetched(renamed, LATER)
    assert repository.cards["sv01-002"] == Fetched(SV01_CARDS[1], START)
    assert repository.sets["sv02"] == Fetched(SV02, START)
    assert run.result is not None
    assert run.result.counts.cards == CardCounts(
        fetched=1, created=0, updated=1, unchanged=0, failed=0
    )


def test_set_and_card_failures_make_a_partial_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="tcg_pokedex")
    provider = catalog()
    provider.fail_set("sv", "sv03", "HTTP 500 after 3 attempts")
    provider.fail_card("sv01-002", "HTTP 404")
    repository = InMemoryCatalogRepository()

    run = sync_catalog(
        provider, repository, InMemorySyncRunRepository(), FakeClock(START)
    )

    assert run.status is RunStatus.PARTIAL
    assert run.result is not None
    assert run.result.failures == (
        Failure(kind="card", provider_id="sv01-002", reason="HTTP 404"),
        Failure(kind="set", provider_id="sv03", reason="HTTP 500 after 3 attempts"),
    )
    assert set(repository.sets) == {"sv01", "sv02"}
    assert "sv01-002" not in repository.cards
    logged = [r.getMessage() for r in caplog.records]
    assert logged.count("sync.failure") == 2


def test_an_unavailable_index_fails_the_run_before_any_write() -> None:
    provider = catalog()
    provider.take_down("HTTP 500 after 3 attempts")
    repository = InMemoryCatalogRepository()
    runs = InMemorySyncRunRepository()

    run = sync_catalog(provider, repository, runs, FakeClock(START))

    assert run.status is RunStatus.FAILED
    assert run.error == "HTTP 500 after 3 attempts"
    assert repository.sets == {}
    assert runs.get_run(run.id, SyncResult) == run


class ExplodingRepository(InMemoryCatalogRepository):
    def save_set(self, batch: SetBatch, fetched_at: datetime) -> None:
        super().save_set(batch, fetched_at)
        raise RuntimeError("connection lost")


def test_an_unexpected_error_fails_the_run_and_still_closes_it() -> None:
    runs = InMemorySyncRunRepository()

    run = sync_catalog(catalog(), ExplodingRepository(), runs, FakeClock(START))

    assert run.status is RunStatus.FAILED
    assert run.error == "connection lost"
    assert runs.get_run(run.id, SyncResult) == run
