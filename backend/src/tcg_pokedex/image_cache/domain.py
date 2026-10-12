"""Image-cache domain: what to fetch for each card, and how a run is counted.

Pure: no I/O and no clock. `plan_card` is the only copy of the pt → English →
unavailable rule; the service carries out the steps it names.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tcg_pokedex.sync_runs.domain import MAX_FAILURES, RunStatus, run_status


class Language(StrEnum):
    PT = "pt"
    EN = "en"


class CardSize(StrEnum):
    SMALL = "small"
    LARGE = "large"


class ArtworkKind(StrEnum):
    LOGO = "logo"
    SYMBOL = "symbol"


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
class StoredCardImage:
    """A card's image row. `language` None means no image in pt or English."""

    language: Language | None
    fetched_at: datetime


@dataclass(frozen=True)
class CardToResolve:
    card_id: str
    pt_image_url: str | None
    stored: StoredCardImage | None
    files_present: bool = False


@dataclass(frozen=True)
class CardImages:
    small: bytes
    large: bytes


@dataclass(frozen=True)
class Missing:
    """The provider has no such asset."""


@dataclass(frozen=True)
class ArtworkToFetch:
    set_id: str
    kind: ArtworkKind
    url: str | None
    cached: bool


@dataclass(frozen=True)
class CardOutcome:
    """How one card resolved. `language` is the downloaded image's, else None."""

    card_id: str
    outcome: Outcome
    language: Language | None = None


def plan_card(card: CardToResolve) -> CardPlan:
    """A pt image on disk is final; an English one is retried only when pt exists."""
    language = card.stored.language if card.stored else None
    if card.files_present and language is Language.PT:
        return CardPlan.SKIP
    if card.files_present and language is Language.EN:
        return CardPlan.TRY_PT_KEEP_EN if card.pt_image_url else CardPlan.SKIP
    return CardPlan.TRY_PT_THEN_EN if card.pt_image_url else CardPlan.TRY_EN


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImageFailure(_Model):
    kind: Literal["card", "logo", "symbol"]
    provider_id: str
    reason: str


class ImageCounts(_Model):
    downloaded: int = Field(ge=0)
    cached: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    failed: int = Field(ge=0)


class ImageSyncCounts(_Model):
    cards: ImageCounts
    artwork: ImageCounts


class ImageSyncResult(_Model):
    """`set_id` is set only on a run started by tracking that set."""

    set_id: str | None
    counts: ImageSyncCounts
    failures: tuple[ImageFailure, ...] = Field(max_length=MAX_FAILURES)


class SetTracking(_Model):
    """A set's tracking state for one owner, and its image progress."""

    set_id: str
    tracked: bool
    total_cards: int = Field(ge=0)
    cached: int = Field(ge=0)
    unavailable: int = Field(ge=0)
    downloading: bool


class ImageResultBuilder:
    """Collects a run's card and artwork counts and failures, and decides its status."""

    def __init__(self, set_id: str | None) -> None:
        self._set_id = set_id
        self._cards: Counter[Outcome] = Counter()
        self._artwork: Counter[Outcome] = Counter()
        self._failed_cards = 0
        self._failed_artwork = 0
        self._failures: list[ImageFailure] = []
        self._aborted = False

    def count_card(self, outcome: Outcome) -> None:
        self._cards[outcome] += 1

    def count_artwork(self, outcome: Outcome) -> None:
        self._artwork[outcome] += 1

    def fail(self, failure: ImageFailure) -> None:
        """Count every failure; keep only the first `MAX_FAILURES` of them."""
        if failure.kind == "card":
            self._failed_cards += 1
        else:
            self._failed_artwork += 1
        if len(self._failures) < MAX_FAILURES:
            self._failures.append(failure)

    def abort(self) -> None:
        self._aborted = True

    def status(self) -> RunStatus:
        return run_status(
            aborted=self._aborted, failed=self._failed_cards + self._failed_artwork
        )

    def build(self) -> ImageSyncResult:
        return ImageSyncResult(
            set_id=self._set_id,
            counts=ImageSyncCounts(
                cards=_counts(self._cards, self._failed_cards),
                artwork=_counts(self._artwork, self._failed_artwork),
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
