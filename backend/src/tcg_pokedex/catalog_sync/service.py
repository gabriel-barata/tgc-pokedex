import logging
from datetime import timedelta
from uuid import uuid4

from tcg_pokedex.catalog_sync.domain import (
    Card,
    Failure,
    ResultBuilder,
    SyncResult,
    is_pocket_series,
    plan_set,
)
from tcg_pokedex.catalog_sync.ports import CatalogProvider, CatalogRepository
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.sync_runs.domain import RunStatus, SyncKind, SyncRun
from tcg_pokedex.sync_runs.ports import SyncRunRepository

logger = logging.getLogger("tcg_pokedex.catalog_sync")


def sync_catalog(
    provider: CatalogProvider,
    repository: CatalogRepository,
    runs: SyncRunRepository,
    clock: Clock,
) -> SyncRun[SyncResult]:
    """Copy the provider's physical catalog into the repository, one set at a time.

    The run is recorded before any catalog write and closed at the end, also when it
    fails. Every row written carries the run's start time as its fetch time. Set and
    card failures are recorded and the run goes on; an unavailable index or any other
    error fails the run, keeping the sets already saved.
    """
    run = SyncRun[SyncResult](
        id=uuid4(),
        kind=SyncKind.CATALOG,
        status=RunStatus.RUNNING,
        started_at=clock.now(),
    )
    runs.start_run(run)
    _log("sync.run.started", run_id=str(run.id), kind=run.kind.value)
    sets = _SetSync(provider, repository, run)
    error = None
    try:
        for set_id in _read_index(provider):
            sets.sync(set_id)
    except Exception as failure:
        error = str(failure)
        sets.result.abort()
    closed = _close(run, sets.result, clock, error)
    runs.finish_run(closed)
    _log(
        "sync.run.finished",
        run_id=str(closed.id),
        status=closed.status.value,
        duration_ms=closed.duration_ms,
        counts=closed.result.counts.model_dump(mode="json") if closed.result else None,
        error=closed.error,
    )
    return closed


def _read_index(provider: CatalogProvider) -> list[str]:
    return [
        set_id
        for series_id in provider.list_series_ids()
        if not is_pocket_series(series_id)
        for set_id in provider.list_set_ids(series_id)
    ]


class _SetSync:
    """Syncs one set at a time, writing each series only the first time."""

    def __init__(
        self,
        provider: CatalogProvider,
        repository: CatalogRepository,
        run: SyncRun[SyncResult],
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._run = run
        self._series_written: set[str] = set()
        self.result = ResultBuilder()

    def sync(self, set_id: str) -> None:
        listing = self._provider.fetch_set(set_id)
        if isinstance(listing, Failure):
            self._fail(listing)
            return
        if not listing.card_ids:
            self.result.skip_set()
            return
        cards: list[Card] = []
        for outcome in self._provider.fetch_cards(set_id, listing.card_ids):
            if isinstance(outcome, Failure):
                self._fail(outcome)
            else:
                cards.append(outcome)
        stored = self._repository.load_stored(
            listing.series.id, set_id, [card.id for card in cards]
        )
        batch, changes = plan_set(stored, listing, cards, self._series_written)
        self._repository.save_set(batch, fetched_at=self._run.started_at)
        self._series_written.add(listing.series.id)
        self.result.record(changes)

    def _fail(self, failure: Failure) -> None:
        self.result.fail(failure)
        _log(
            "sync.failure",
            run_id=str(self._run.id),
            kind=failure.kind,
            provider_id=failure.provider_id,
            reason=failure.reason,
        )


def _close(
    run: SyncRun[SyncResult], result: ResultBuilder, clock: Clock, error: str | None
) -> SyncRun[SyncResult]:
    finished_at = clock.now()
    return SyncRun[SyncResult](
        id=run.id,
        kind=run.kind,
        source=run.source,
        status=result.status(),
        started_at=run.started_at,
        finished_at=finished_at,
        duration_ms=(finished_at - run.started_at) // timedelta(milliseconds=1),
        result=result.build(),
        error=error,
    )


def _log(event: str, **fields: object) -> None:
    logger.info(event, extra={"fields": fields})
