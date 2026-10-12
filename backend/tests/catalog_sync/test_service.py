import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tcg_pokedex.catalog_sync.domain import (
    Card,
    CardCounts,
    Failure,
    Fetched,
    KindCounts,
    RunStatus,
    SetCounts,
    SyncKind,
    Variant,
)
from tcg_pokedex.catalog_sync.fakes import (
    InMemoryCatalogProvider,
    InMemoryCatalogRepository,
)
from tcg_pokedex.catalog_sync.service import sync_catalog
from tcg_pokedex.clock.fake import FakeClock
from tests.catalog_sync.builders import make_card, make_listing, make_series, make_set

START = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)

SV = make_series()
XY = make_series(id="xy", name="XY")
SV01 = make_set()
SV02 = make_set(id="sv02", name="Evoluções em Paldea")
XY0 = make_set(id="xy0", series_id="xy", name="Conjunto para Iniciantes Kalos")
SV01_CARDS = (
    make_card(),
    make_card(id="sv01-002", collector_number="002", name="Heracross"),
)
SV02_CARDS = (make_card(id="sv02-001", set_id="sv02", name="Sprigatito"),)
XY0_CARDS = (
    make_card(
        id="xy0-1",
        set_id="xy0",
        collector_number="1",
        name="Weedle",
        rarity=None,
        variants=[Variant.NORMAL],
    ),
)


def catalog() -> InMemoryCatalogProvider:
    """base (empty base1), xy (xy0), sv (sv01, sv02) and the Pocket series tcgp (A1)."""
    provider = InMemoryCatalogProvider()
    provider.add_set(
        make_listing(
            card_set=make_set(id="base1", series_id="base", name="Coleção Básica"),
            series=make_series(id="base", name="Coleção Básica"),
        )
    )
    provider.add_set(
        make_listing(card_set=XY0, series=XY, card_ids=["xy0-1"]), XY0_CARDS
    )
    provider.add_set(
        make_listing(card_set=SV01, card_ids=["sv01-001", "sv01-002"]), SV01_CARDS
    )
    provider.add_set(make_listing(card_set=SV02, card_ids=["sv02-001"]), SV02_CARDS)
    pocket_card = make_card(id="A1-001", set_id="A1", collector_number="001")
    provider.add_set(
        make_listing(
            card_set=make_set(id="A1", series_id="tcgp", name="Dominação Genética"),
            series=make_series(id="tcgp", name="Pokémon Estampas Ilustradas Pocket"),
            card_ids=["A1-001"],
        ),
        [pocket_card],
    )
    return provider


class SlowCards(InMemoryCatalogProvider):
    """Advances the clock while it fetches cards, as real requests take time."""

    def __init__(self, clock: FakeClock, took: timedelta) -> None:
        super().__init__()
        self._clock = clock
        self._took = took

    def fetch_cards(self, set_id: str, card_ids: Sequence[str]) -> list[Card | Failure]:
        self._clock.advance(self._took)
        return super().fetch_cards(set_id, card_ids)


def fields(record: logging.LogRecord) -> dict[str, Any]:
    return record.__dict__["fields"]


def test_an_empty_store_ends_with_every_physical_set_with_cards() -> None:
    repository = InMemoryCatalogRepository()

    sync_catalog(catalog(), repository, FakeClock(START))

    assert repository.series == {"sv": Fetched(SV, START), "xy": Fetched(XY, START)}
    assert repository.sets == {
        "xy0": Fetched(XY0, START),
        "sv01": Fetched(SV01, START),
        "sv02": Fetched(SV02, START),
    }
    assert repository.cards == {
        card.id: Fetched(card, START) for card in XY0_CARDS + SV01_CARDS + SV02_CARDS
    }


def test_a_first_run_reports_everything_created_and_succeeds() -> None:
    run = sync_catalog(catalog(), InMemoryCatalogRepository(), FakeClock(START))

    assert run.status is RunStatus.SUCCEEDED
    assert run.kind is SyncKind.CATALOG
    assert run.error is None
    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=2, created=2, updated=0, unchanged=0
    )
    assert run.result.counts.sets == SetCounts(
        fetched=3, created=3, updated=0, unchanged=0, skipped=1, failed=0
    )
    assert run.result.counts.cards == CardCounts(
        fetched=4, created=4, updated=0, unchanged=0, failed=0
    )
    assert run.result.failures == ()


def test_the_run_is_recorded_before_any_write_and_closed_after() -> None:
    repository = InMemoryCatalogRepository()

    run = sync_catalog(catalog(), repository, FakeClock(START))

    assert repository.calls == [
        "start_run",
        "save_set",
        "save_set",
        "save_set",
        "finish_run",
    ]
    assert repository.get_run(run.id) == run


def test_the_run_is_timed_with_the_clock() -> None:
    clock = FakeClock(START)
    provider = SlowCards(clock, timedelta(milliseconds=1500))
    provider.add_set(make_listing(card_ids=["sv01-001"]), [make_card()])

    run = sync_catalog(provider, InMemoryCatalogRepository(), clock)

    assert run.started_at == START
    assert run.finished_at == START + timedelta(milliseconds=1500)
    assert run.duration_ms == 1500


def test_every_row_is_stamped_with_the_run_start() -> None:
    clock = FakeClock(START)
    provider = SlowCards(clock, timedelta(seconds=5))
    provider.add_set(make_listing(card_ids=["sv01-001"]), [make_card()])
    provider.add_set(make_listing(card_set=SV02, card_ids=["sv02-001"]), SV02_CARDS)
    repository = InMemoryCatalogRepository()

    sync_catalog(provider, repository, clock)

    stamps = {
        stored.fetched_at
        for rows in (repository.series, repository.sets, repository.cards)
        for stored in rows.values()
    }
    assert stamps == {START}


def test_pocket_series_are_never_requested_stored_or_counted() -> None:
    provider = catalog()
    repository = InMemoryCatalogRepository()

    run = sync_catalog(provider, repository, FakeClock(START))

    assert not [path for path in provider.requests if "tcgp" in path or "A1" in path]
    assert "tcgp" not in repository.series
    assert "A1" not in repository.sets
    assert run.result is not None
    assert run.result.counts.sets.fetched + run.result.counts.sets.skipped == 4


def test_the_whole_index_is_read_before_any_set() -> None:
    provider = catalog()

    sync_catalog(provider, InMemoryCatalogRepository(), FakeClock(START))

    assert provider.requests[:4] == ["series", "series/base", "series/xy", "series/sv"]


def test_an_empty_set_is_skipped_without_requesting_cards() -> None:
    provider = catalog()
    repository = InMemoryCatalogRepository()

    sync_catalog(provider, repository, FakeClock(START))

    assert "sets/base1" in provider.requests
    assert "base1" not in repository.sets


def test_a_series_whose_sets_are_all_skipped_is_not_stored() -> None:
    repository = InMemoryCatalogRepository()

    sync_catalog(catalog(), repository, FakeClock(START))

    assert "base" not in repository.series


def test_a_series_with_two_stored_sets_is_written_and_counted_once() -> None:
    provider = InMemoryCatalogProvider()
    provider.add_set(make_listing(card_ids=["sv01-001"]), [make_card()])
    provider.add_set(make_listing(card_set=SV02, card_ids=["sv02-001"]), SV02_CARDS)

    run = sync_catalog(provider, InMemoryCatalogRepository(), FakeClock(START))

    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=1, created=1, updated=0, unchanged=0
    )


def test_a_normal_and_reverse_card_keeps_both_variants() -> None:
    repository = InMemoryCatalogRepository()

    sync_catalog(catalog(), repository, FakeClock(START))

    assert repository.cards["sv01-001"].value.variants == {
        Variant.NORMAL,
        Variant.REVERSE,
    }


def test_the_run_start_and_end_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="tcg_pokedex")

    run = sync_catalog(catalog(), InMemoryCatalogRepository(), FakeClock(START))

    records = [r for r in caplog.records if r.name.startswith("tcg_pokedex")]
    assert [r.getMessage() for r in records] == [
        "sync.run.started",
        "sync.run.finished",
    ]
    started, finished = records
    assert fields(started) == {"run_id": str(run.id), "kind": "catalog"}
    assert run.result is not None
    assert fields(finished) == {
        "run_id": str(run.id),
        "status": "succeeded",
        "duration_ms": 0,
        "counts": run.result.counts.model_dump(mode="json"),
        "error": None,
    }


LATER = START + timedelta(hours=1)


def sv01_only(cards: Sequence[Card] = SV01_CARDS) -> InMemoryCatalogProvider:
    provider = InMemoryCatalogProvider()
    provider.add_set(
        make_listing(card_set=SV01, card_ids=[card.id for card in cards]), cards
    )
    return provider


def test_a_second_run_over_the_same_data_reports_everything_unchanged() -> None:
    repository = InMemoryCatalogRepository()
    sync_catalog(catalog(), repository, FakeClock(START))

    run = sync_catalog(catalog(), repository, FakeClock(LATER))

    assert run.status is RunStatus.SUCCEEDED
    assert run.result is not None
    assert run.result.counts.series == KindCounts(
        fetched=2, created=0, updated=0, unchanged=2
    )
    assert run.result.counts.sets == SetCounts(
        fetched=3, created=0, updated=0, unchanged=3, skipped=1, failed=0
    )
    assert run.result.counts.cards == CardCounts(
        fetched=4, created=0, updated=0, unchanged=4, failed=0
    )
    stamps = {
        stored.fetched_at
        for rows in (repository.series, repository.sets, repository.cards)
        for stored in rows.values()
    }
    assert stamps == {LATER}


def test_a_card_renamed_at_the_provider_is_updated() -> None:
    repository = InMemoryCatalogRepository()
    sync_catalog(sv01_only(), repository, FakeClock(START))
    renamed = make_card(name="Pineco Renomeado")

    run = sync_catalog(
        sv01_only([renamed, SV01_CARDS[1]]), repository, FakeClock(LATER)
    )

    assert repository.cards["sv01-001"] == Fetched(renamed, LATER)
    assert run.result is not None
    assert run.result.counts.cards == CardCounts(
        fetched=2, created=0, updated=1, unchanged=1, failed=0
    )


def test_rows_the_provider_no_longer_lists_are_left_as_they_were() -> None:
    repository = InMemoryCatalogRepository()
    sync_catalog(catalog(), repository, FakeClock(START))
    before = dict(repository.cards)

    sync_catalog(sv01_only(SV01_CARDS[:1]), repository, FakeClock(LATER))

    assert repository.cards["sv01-002"] == before["sv01-002"]
    assert repository.sets["sv02"] == Fetched(SV02, START)
    assert repository.sets["xy0"] == Fetched(XY0, START)
    assert repository.cards["sv02-001"] == before["sv02-001"]
    assert repository.series["xy"] == Fetched(XY, START)


def test_a_set_that_now_lists_no_cards_is_skipped_and_left_untouched() -> None:
    repository = InMemoryCatalogRepository()
    sync_catalog(sv01_only(), repository, FakeClock(START))
    before = (dict(repository.series), dict(repository.sets), dict(repository.cards))

    run = sync_catalog(sv01_only([]), repository, FakeClock(LATER))

    assert run.result is not None
    assert run.result.counts.sets.skipped == 1
    assert run.result.counts.sets.fetched == 0
    assert (repository.series, repository.sets, repository.cards) == before


def test_a_series_seen_again_counts_as_unchanged_once() -> None:
    repository = InMemoryCatalogRepository()
    sync_catalog(catalog(), repository, FakeClock(START))

    run = sync_catalog(catalog(), repository, FakeClock(LATER))

    assert run.result is not None
    assert run.result.counts.series.unchanged == 2
    assert repository.series["sv"] == Fetched(SV, LATER)
