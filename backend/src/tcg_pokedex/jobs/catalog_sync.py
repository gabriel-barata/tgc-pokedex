"""`tcg sync catalog`: copy the TCGdex pt catalog into our tables, one set at a time."""

from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from typing import Any

from sqlalchemy import Engine

from tcg_pokedex.jobs.runs import close_run, finish_run, log, run_status, start_run
from tcg_pokedex.models.catalog import save_set
from tcg_pokedex.providers.tcgdex import (
    MAX_IN_FLIGHT,
    Card,
    CardSet,
    Series,
    Tcgdex,
    TcgdexError,
)
from tcg_pokedex.views.ownership import Variant
from tcg_pokedex.views.sync import (
    MAX_FAILURES,
    CardCounts,
    Failure,
    KindCounts,
    RunStatus,
    SetCounts,
    SyncCounts,
    SyncKind,
    SyncResult,
    SyncRun,
)

POCKET_SERIES_ID = "tcgp"

Row = dict[str, Any]


def is_pocket_series(series_id: str) -> bool:
    """TCG Pocket sets are never synced. This is the only definition of the rule."""
    return series_id == POCKET_SERIES_ID


class Change(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


def classify(stored: Row | None, fetched: Row) -> Change:
    """Compare every entity column. Source and fetched-at are not entity columns."""
    if stored is None:
        return Change.CREATED
    return Change.UNCHANGED if stored == fetched else Change.UPDATED


class ResultBuilder:
    """Collects a run's counts and failures, and decides its status."""

    def __init__(self) -> None:
        self._series: Counter[Change] = Counter()
        self._sets: Counter[Change] = Counter()
        self._cards: Counter[Change] = Counter()
        self._skipped_sets = 0
        self._failed: Counter[str] = Counter()
        self._failures: list[Failure] = []
        self._aborted = False

    def record(
        self, series: Change | None, card_set: Change, cards: Sequence[Change]
    ) -> None:
        if series is not None:
            self._series[series] += 1
        self._sets[card_set] += 1
        self._cards.update(cards)

    def skip_set(self) -> None:
        self._skipped_sets += 1

    def fail(self, failure: Failure) -> None:
        """Count every failure; keep only the first `MAX_FAILURES` of them."""
        self._failed[failure.kind] += 1
        if len(self._failures) < MAX_FAILURES:
            self._failures.append(failure)

    def abort(self) -> None:
        self._aborted = True

    def status(self) -> RunStatus:
        return run_status(aborted=self._aborted, failed=self._failed.total())

    def build(self) -> SyncResult:
        return SyncResult(
            counts=SyncCounts(
                series=KindCounts(**_change_counts(self._series)),
                sets=SetCounts(
                    **_change_counts(self._sets),
                    skipped=self._skipped_sets,
                    failed=self._failed["set"],
                ),
                cards=CardCounts(
                    **_change_counts(self._cards), failed=self._failed["card"]
                ),
            ),
            failures=tuple(self._failures),
        )


def _change_counts(changes: Counter[Change]) -> dict[str, int]:
    return {
        "fetched": changes.total(),
        "created": changes[Change.CREATED],
        "updated": changes[Change.UPDATED],
        "unchanged": changes[Change.UNCHANGED],
    }


def sync_catalog(
    engine: Engine,
    tcgdex: Tcgdex,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SyncRun[SyncResult]:
    """Copy the TCGdex physical catalog into our tables, one set at a time.

    The run is recorded before any catalog write and closed at the end, also when it
    fails. Every row written carries the run's start time as its fetch time. Set and
    card failures are recorded and the run goes on; an unavailable index or any other
    error fails the run, keeping the sets already saved.
    """
    run = start_run(engine, SyncKind.CATALOG, now(), SyncResult)
    job = _CatalogSync(engine, tcgdex, run)
    error = None
    try:
        with ThreadPoolExecutor(max_workers=MAX_IN_FLIGHT) as pool:
            for set_id in _read_index(tcgdex):
                job.sync_set(pool, set_id)
    except Exception as failure:
        error = str(failure)
        job.result.abort()
    closed = close_run(
        run,
        status=job.result.status(),
        result=job.result.build(),
        error=error,
        finished_at=now(),
    )
    return finish_run(engine, closed)


def _read_index(tcgdex: Tcgdex) -> list[str]:
    return [
        set_id
        for series_id in tcgdex.series_ids()
        if not is_pocket_series(series_id)
        for set_id in tcgdex.set_ids(series_id)
    ]


class _CatalogSync:
    """Syncs one set at a time, writing each series only the first time."""

    def __init__(
        self, engine: Engine, tcgdex: Tcgdex, run: SyncRun[SyncResult]
    ) -> None:
        self._engine = engine
        self._tcgdex = tcgdex
        self._run = run
        self._series_written: set[str] = set()
        self.result = ResultBuilder()

    def sync_set(self, pool: ThreadPoolExecutor, set_id: str) -> None:
        try:
            listing = self._tcgdex.set_listing(set_id)
        except TcgdexError as error:
            self._fail(Failure(kind="set", provider_id=set_id, reason=error.reason))
            return
        if not listing.card_ids:
            self.result.skip_set()
            return
        fetched: list[Card] = []
        for outcome in pool.map(partial(self._card, set_id), listing.card_ids):
            if isinstance(outcome, Failure):
                self._fail(outcome)
            else:
                fetched.append(outcome)
        write_series = listing.series.id not in self._series_written
        series_row = _series_row(listing.series)
        set_row = _set_row(listing.card_set)
        card_rows = [_card_row(card) for card in fetched]
        stored = save_set(
            self._engine,
            series_row=series_row if write_series else None,
            set_row=set_row,
            card_rows=card_rows,
            fetched_at=self._run.started_at,
        )
        self._series_written.add(listing.series.id)
        self.result.record(
            classify(stored.series, series_row) if write_series else None,
            classify(stored.card_set, set_row),
            [classify(stored.cards.get(row["id"]), row) for row in card_rows],
        )

    def _card(self, set_id: str, card_id: str) -> Card | Failure:
        try:
            return self._tcgdex.card(card_id, set_id)
        except TcgdexError as error:
            return Failure(kind="card", provider_id=card_id, reason=error.reason)

    def _fail(self, failure: Failure) -> None:
        self.result.fail(failure)
        log(
            "sync.failure",
            run_id=str(self._run.id),
            kind=failure.kind,
            provider_id=failure.provider_id,
            reason=failure.reason,
        )


def _series_row(item: Series) -> Row:
    return {"id": item.id, "name": item.name}


def _set_row(card_set: CardSet) -> Row:
    return {
        "id": card_set.id,
        "series_id": card_set.series_id,
        "name": card_set.name,
        "release_date": card_set.release_date,
        "official_count": card_set.official_count,
        "total_count": card_set.total_count,
        "logo_url": card_set.logo_url,
        "symbol_url": card_set.symbol_url,
    }


def _card_row(card: Card) -> Row:
    return {
        "id": card.id,
        "set_id": card.set_id,
        "collector_number": card.collector_number,
        "name": card.name,
        "rarity": card.rarity,
        "illustrator": card.illustrator,
        "image_url": card.image_url,
        "variants": [variant.value for variant in Variant if variant in card.variants],
    }
