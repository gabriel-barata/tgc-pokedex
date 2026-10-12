import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import uuid4

from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.image_cache.domain import (
    ArtworkToFetch,
    CardImages,
    CardOutcome,
    CardPlan,
    CardToResolve,
    ImageFailure,
    ImageResultBuilder,
    ImageSyncResult,
    Language,
    Missing,
    Outcome,
    plan_card,
)
from tcg_pokedex.image_cache.ports import (
    ImageCacheRepository,
    ImageProvider,
    ImageStore,
)
from tcg_pokedex.sync_runs.domain import RunStatus, SyncKind, SyncRun
from tcg_pokedex.sync_runs.ports import SyncRunRepository

WORKERS = 8

logger = logging.getLogger("tcg_pokedex.image_cache")


@dataclass(frozen=True)
class ImageSyncPorts:
    """Everything an image run reads from and writes to."""

    provider: ImageProvider
    store: ImageStore
    repository: ImageCacheRepository
    runs: SyncRunRepository


def sync_images(
    ports: ImageSyncPorts, clock: Clock, set_id: str | None = None
) -> SyncRun[ImageSyncResult]:
    """Cache the card images of `set_id`, or of every tracked set when it is None.

    A run with no `set_id` also caches every stored set's logo and symbol.

    The run is recorded before any download and closed at the end, also when it
    fails. Every row written carries the run's start time as its fetch time. A failed
    image is recorded and the run goes on; an unusable store or any other error fails
    the run, keeping what was already saved.
    """
    run = SyncRun[ImageSyncResult](
        id=uuid4(),
        kind=SyncKind.IMAGES,
        status=RunStatus.RUNNING,
        started_at=clock.now(),
    )
    ports.runs.start_run(run)
    _log("sync.run.started", run_id=str(run.id), kind=run.kind.value, set_id=set_id)
    job = _ImageSync(ports, run, ImageResultBuilder(set_id))
    error = None
    try:
        ports.store.check_writable()
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            set_ids = [set_id] if set_id else ports.repository.tracked_set_ids()
            for each in set_ids:
                job.sync_cards(pool, each)
            if set_id is None:
                job.sync_artwork(pool)
    except Exception as failure:
        error = str(failure)
        job.result.abort()
    closed = _close(run, job.result, clock, error)
    ports.runs.finish_run(closed)
    _log(
        "sync.run.finished",
        run_id=str(closed.id),
        status=closed.status.value,
        duration_ms=closed.duration_ms,
        counts=closed.result.counts.model_dump(mode="json") if closed.result else None,
        error=closed.error,
    )
    return closed


class _ImageSync:
    """Resolves cards on a pool of workers; database writes stay on this thread."""

    def __init__(
        self,
        ports: ImageSyncPorts,
        run: SyncRun[ImageSyncResult],
        result: ImageResultBuilder,
    ) -> None:
        self._provider = ports.provider
        self._store = ports.store
        self._repository = ports.repository
        self._run = run
        self.result = result

    def sync_cards(self, pool: Executor, set_id: str) -> None:
        cards = [
            replace(card, files_present=self._store.has_card(card.card_id))
            for card in self._repository.cards_to_resolve(set_id)
        ]
        rows: list[tuple[str, Language | None]] = []
        for outcome in pool.map(self._resolve, cards):
            if isinstance(outcome, ImageFailure):
                self._fail(outcome)
                continue
            self.result.count_card(outcome.outcome)
            if outcome.outcome is not Outcome.CACHED:
                rows.append((outcome.card_id, outcome.language))
        self._repository.save_card_images(rows, fetched_at=self._run.started_at)

    def sync_artwork(self, pool: Executor) -> None:
        to_fetch: list[ArtworkToFetch] = []
        for artwork in self._repository.artwork_to_fetch():
            if artwork.cached:
                self.result.count_artwork(Outcome.CACHED)
            else:
                to_fetch.append(artwork)
        outcomes = pool.map(self._fetch_artwork, to_fetch)
        for artwork, outcome in zip(to_fetch, outcomes, strict=True):
            if isinstance(outcome, ImageFailure):
                self._fail(outcome)
                continue
            if outcome is Outcome.DOWNLOADED:
                self._repository.save_artwork(
                    artwork.set_id, artwork.kind, fetched_at=self._run.started_at
                )
            self.result.count_artwork(outcome)

    def _fetch_artwork(self, artwork: ArtworkToFetch) -> Outcome | ImageFailure:
        if artwork.url is None:
            return Outcome.UNAVAILABLE
        content = self._provider.fetch_artwork(
            artwork.set_id, artwork.kind, artwork.url
        )
        if isinstance(content, bytes):
            self._store.put_artwork(artwork.set_id, artwork.kind, content)
            return Outcome.DOWNLOADED
        return Outcome.UNAVAILABLE if isinstance(content, Missing) else content

    def _resolve(self, card: CardToResolve) -> CardOutcome | ImageFailure:
        plan = plan_card(card)
        if plan is CardPlan.SKIP:
            return CardOutcome(card.card_id, Outcome.CACHED)
        if plan is CardPlan.TRY_EN or card.pt_image_url is None:
            return self._try_english(card.card_id)
        pt = self._download(card.card_id, card.pt_image_url, Language.PT)
        if not isinstance(pt, Missing):
            return pt
        if plan is CardPlan.TRY_PT_KEEP_EN:
            return CardOutcome(card.card_id, Outcome.CACHED)
        return self._try_english(card.card_id)

    def _try_english(self, card_id: str) -> CardOutcome | ImageFailure:
        base_url = self._provider.english_image_url(card_id)
        if base_url is None:
            return CardOutcome(card_id, Outcome.UNAVAILABLE)
        if isinstance(base_url, ImageFailure):
            return base_url
        english = self._download(card_id, base_url, Language.EN)
        if isinstance(english, Missing):
            return CardOutcome(card_id, Outcome.UNAVAILABLE)
        return english

    def _download(
        self, card_id: str, base_url: str, language: Language
    ) -> CardOutcome | Missing | ImageFailure:
        images = self._provider.fetch_card_images(card_id, base_url)
        if not isinstance(images, CardImages):
            return images
        self._store.put_card(card_id, images)
        return CardOutcome(card_id, Outcome.DOWNLOADED, language)

    def _fail(self, failure: ImageFailure) -> None:
        self.result.fail(failure)
        _log(
            "sync.failure",
            run_id=str(self._run.id),
            kind=failure.kind,
            provider_id=failure.provider_id,
            reason=failure.reason,
        )


def _close(
    run: SyncRun[ImageSyncResult],
    result: ImageResultBuilder,
    clock: Clock,
    error: str | None,
) -> SyncRun[ImageSyncResult]:
    finished_at = clock.now()
    return run.model_copy(
        update={
            "status": result.status(),
            "finished_at": finished_at,
            "duration_ms": (finished_at - run.started_at) // timedelta(milliseconds=1),
            "result": result.build(),
            "error": error,
        }
    )


def _log(event: str, **fields: object) -> None:
    logger.info(event, extra={"fields": fields})
