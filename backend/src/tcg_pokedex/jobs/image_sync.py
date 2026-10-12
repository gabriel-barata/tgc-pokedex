"""`tcg sync images` and track-triggered downloads: cache card images and artwork."""

from collections import Counter
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import Engine

from tcg_pokedex.jobs.image_store import (
    card_path,
    check_writable,
    item_folder,
    write_file,
)
from tcg_pokedex.jobs.runs import close_run, finish_run, log, run_status, start_run
from tcg_pokedex.models.images import (
    artwork_sources,
    cached_artwork,
    cards_with_image_language,
    save_artwork,
    save_card_images,
)
from tcg_pokedex.models.tracking import tracked_set_ids
from tcg_pokedex.providers.tcgdex import Tcgdex, TcgdexError
from tcg_pokedex.views.images import ArtworkKind, CardSize
from tcg_pokedex.views.sync import (
    MAX_FAILURES,
    ImageCounts,
    ImageFailure,
    ImageSyncCounts,
    ImageSyncResult,
    RunStatus,
    SyncKind,
    SyncRun,
)

WORKERS = 8


class Language(StrEnum):
    PT = "pt"
    EN = "en"


class CardPlan(StrEnum):
    """What a run does for one card.

    `try_pt_then_en`: fetch pt; when missing, `try_en`. `try_pt_keep_en`: fetch pt;
    when missing, keep the English image. `try_en`: look up the English image; none
    means unavailable.
    """

    SKIP = "skip"
    TRY_PT_KEEP_EN = "try_pt_keep_en"
    TRY_PT_THEN_EN = "try_pt_then_en"
    TRY_EN = "try_en"


class Outcome(StrEnum):
    DOWNLOADED = "downloaded"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CardToResolve:
    """A card with its pt image URL and the language of its stored image, if any."""

    card_id: str
    pt_image_url: str | None
    language: Language | None
    files_present: bool


def plan_card(card: CardToResolve) -> CardPlan:
    """A pt image on disk is final; an English one is retried only when pt exists."""
    if card.files_present and card.language is Language.PT:
        return CardPlan.SKIP
    if card.files_present and card.language is Language.EN:
        return CardPlan.TRY_PT_KEEP_EN if card.pt_image_url else CardPlan.SKIP
    return CardPlan.TRY_PT_THEN_EN if card.pt_image_url else CardPlan.TRY_EN


class ImageResultBuilder:
    """Collects a run's card and artwork counts and failures, and decides its status."""

    def __init__(self, set_id: str | None) -> None:
        self._set_id = set_id
        self._cards: Counter[Outcome] = Counter()
        self._artwork: Counter[Outcome] = Counter()
        self._failed: Counter[bool] = Counter()
        self._failures: list[ImageFailure] = []
        self._aborted = False

    def count_card(self, outcome: Outcome) -> None:
        self._cards[outcome] += 1

    def count_artwork(self, outcome: Outcome) -> None:
        self._artwork[outcome] += 1

    def fail(self, failure: ImageFailure) -> None:
        """Count every failure; keep only the first `MAX_FAILURES` of them."""
        self._failed[failure.kind == "card"] += 1
        if len(self._failures) < MAX_FAILURES:
            self._failures.append(failure)

    def abort(self) -> None:
        self._aborted = True

    def status(self) -> RunStatus:
        return run_status(aborted=self._aborted, failed=self._failed.total())

    def build(self) -> ImageSyncResult:
        return ImageSyncResult(
            set_id=self._set_id,
            counts=ImageSyncCounts(
                cards=_counts(self._cards, self._failed[True]),
                artwork=_counts(self._artwork, self._failed[False]),
            ),
            failures=tuple(self._failures),
        )


def _counts(outcomes: Counter[Outcome], failed: int) -> ImageCounts:
    return ImageCounts(
        downloaded=outcomes[Outcome.DOWNLOADED],
        cached=outcomes[Outcome.CACHED],
        unavailable=outcomes[Outcome.UNAVAILABLE],
        failed=failed,
    )


def sync_images(
    engine: Engine,
    tcgdex: Tcgdex,
    image_dir: Path,
    set_id: str | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SyncRun[ImageSyncResult]:
    """Cache the card images of `set_id`, or of every tracked set when it is None.

    A run with no `set_id` also caches every stored set's logo and symbol.

    The run is recorded before any download and closed at the end, also when it
    fails. Every row written carries the run's start time as its fetch time. A failed
    image is recorded and the run goes on; an unusable image directory or any other
    error fails the run, keeping what was already saved.
    """
    run = start_run(engine, SyncKind.IMAGES, now(), ImageSyncResult, set_id=set_id)
    job = _ImageSync(engine, tcgdex, image_dir, run, ImageResultBuilder(set_id))
    error = None
    try:
        check_writable(image_dir)
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for each in [set_id] if set_id else tracked_set_ids(engine):
                job.sync_cards(pool, each)
            if set_id is None:
                job.sync_artwork(pool)
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


@dataclass(frozen=True)
class _CardOutcome:
    card_id: str
    outcome: Outcome
    language: Language | None = None


class _ImageSync:
    """Downloads on a pool of workers; database writes stay on this thread."""

    def __init__(
        self,
        engine: Engine,
        tcgdex: Tcgdex,
        image_dir: Path,
        run: SyncRun[ImageSyncResult],
        result: ImageResultBuilder,
    ) -> None:
        self._engine = engine
        self._tcgdex = tcgdex
        self._image_dir = image_dir
        self._run = run
        self.result = result

    def sync_cards(self, pool: Executor, set_id: str) -> None:
        rows: list[dict[str, object]] = []
        for outcome in pool.map(self._resolve, self._cards_to_resolve(set_id)):
            if isinstance(outcome, ImageFailure):
                self._fail(outcome)
                continue
            self.result.count_card(outcome.outcome)
            if outcome.outcome is not Outcome.CACHED:
                rows.append(
                    {
                        "card_id": outcome.card_id,
                        "language": outcome.language,
                        "fetched_at": self._run.started_at,
                    }
                )
        if rows:
            save_card_images(self._engine, rows)

    def sync_artwork(self, pool: Executor) -> None:
        catalog = artwork_sources(self._engine)
        cached = cached_artwork(self._engine)
        to_fetch: list[tuple[str, ArtworkKind, str | None]] = []
        for set_id, logo_url, symbol_url in catalog:
            for kind in ArtworkKind:
                if (set_id, kind.value) in cached:
                    self.result.count_artwork(Outcome.CACHED)
                else:
                    url = logo_url if kind is ArtworkKind.LOGO else symbol_url
                    to_fetch.append((set_id, kind, url))
        outcomes = pool.map(self._fetch_artwork, to_fetch)
        for (set_id, kind, _), outcome in zip(to_fetch, outcomes, strict=True):
            if isinstance(outcome, ImageFailure):
                self._fail(outcome)
                continue
            if outcome is Outcome.DOWNLOADED:
                self._save_artwork(set_id, kind)
            self.result.count_artwork(outcome)

    def _cards_to_resolve(self, set_id: str) -> list[CardToResolve]:
        return [
            CardToResolve(
                card_id=card_id,
                pt_image_url=image_url,
                language=None if language is None else Language(language),
                files_present=all(
                    card_path(self._image_dir, card_id, size) for size in CardSize
                ),
            )
            for card_id, image_url, language in cards_with_image_language(
                self._engine, set_id
            )
        ]

    def _save_artwork(self, set_id: str, kind: ArtworkKind) -> None:
        save_artwork(self._engine, set_id, kind, self._run.started_at)

    def _fetch_artwork(
        self, item: tuple[str, ArtworkKind, str | None]
    ) -> Outcome | ImageFailure:
        set_id, kind, url = item
        if url is None:
            return Outcome.UNAVAILABLE
        try:
            content = self._tcgdex.artwork(kind, url)
        except TcgdexError as error:
            return ImageFailure(
                kind=kind.value, provider_id=set_id, reason=error.reason
            )
        if content is None:
            return Outcome.UNAVAILABLE
        write_file(item_folder(self._image_dir, "sets", set_id), kind, content)
        return Outcome.DOWNLOADED

    def _resolve(self, card: CardToResolve) -> _CardOutcome | ImageFailure:
        try:
            return self._resolve_or_raise(card)
        except TcgdexError as error:
            return ImageFailure(
                kind="card", provider_id=card.card_id, reason=error.reason
            )

    def _resolve_or_raise(self, card: CardToResolve) -> _CardOutcome:
        plan = plan_card(card)
        if plan is CardPlan.SKIP:
            return _CardOutcome(card.card_id, Outcome.CACHED)
        if plan is not CardPlan.TRY_EN and card.pt_image_url is not None:
            if self._download(card.card_id, card.pt_image_url):
                return _CardOutcome(card.card_id, Outcome.DOWNLOADED, Language.PT)
            if plan is CardPlan.TRY_PT_KEEP_EN:
                return _CardOutcome(card.card_id, Outcome.CACHED)
        base_url = self._tcgdex.english_image_url(card.card_id)
        if base_url is not None and self._download(card.card_id, base_url):
            return _CardOutcome(card.card_id, Outcome.DOWNLOADED, Language.EN)
        return _CardOutcome(card.card_id, Outcome.UNAVAILABLE)

    def _download(self, card_id: str, base_url: str) -> bool:
        """Store both sizes of the image at `base_url`; False when it is absent."""
        images = self._tcgdex.card_images(base_url)
        if images is None:
            return False
        folder = item_folder(self._image_dir, "cards", card_id)
        write_file(folder, CardSize.SMALL, images[0])
        write_file(folder, CardSize.LARGE, images[1])
        return True

    def _fail(self, failure: ImageFailure) -> None:
        self.result.fail(failure)
        log(
            "sync.failure",
            run_id=str(self._run.id),
            kind=failure.kind,
            provider_id=failure.provider_id,
            reason=failure.reason,
        )
