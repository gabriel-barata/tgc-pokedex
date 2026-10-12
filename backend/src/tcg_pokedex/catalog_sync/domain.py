"""Catalog-sync domain: the catalog entities, the run result and the sync rules.

Pure: no I/O and no clock. The run result is a Pydantic model so its shape is defined
once and validated both when written and when read.
"""

from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tcg_pokedex.sync_runs.domain import MAX_FAILURES, RunStatus, run_status

POCKET_SERIES_ID = "tcgp"


class Variant(StrEnum):
    """A printing a card exists in. Declaration order is the canonical storage order."""

    NORMAL = "normal"
    REVERSE = "reverse"
    HOLO = "holo"
    FIRST_EDITION = "first_edition"
    W_PROMO = "w_promo"


def is_pocket_series(series_id: str) -> bool:
    """TCG Pocket sets are never synced. This is the only definition of the rule."""
    return series_id == POCKET_SERIES_ID


@dataclass(frozen=True)
class Series:
    id: str
    name: str


@dataclass(frozen=True)
class CardSet:
    id: str
    series_id: str
    name: str
    release_date: date
    official_count: int
    total_count: int
    logo_url: str | None
    symbol_url: str | None


@dataclass(frozen=True)
class Card:
    id: str
    set_id: str
    collector_number: str
    name: str
    rarity: str | None
    illustrator: str | None
    image_url: str | None
    variants: frozenset[Variant]

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("a card needs at least one variant")


@dataclass(frozen=True)
class SetListing:
    """One set as the provider returns it: the set, its series and its card ids."""

    card_set: CardSet
    series: Series
    card_ids: tuple[str, ...]


@dataclass(frozen=True)
class Fetched[T]:
    """A stored row with the time it was last fetched."""

    value: T
    fetched_at: datetime


@dataclass(frozen=True)
class StoredCatalog:
    """What the store already holds for one set, its series and its cards."""

    series: Fetched[Series] | None
    card_set: Fetched[CardSet] | None
    cards: Mapping[str, Fetched[Card]]


@dataclass(frozen=True)
class SetBatch:
    """One set's write. `series` is None when this run already wrote it."""

    series: Series | None
    card_set: CardSet
    cards: tuple[Card, ...]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Failure(_Model):
    kind: Literal["set", "card"]
    provider_id: str
    reason: str


class KindCounts(_Model):
    """`fetched` counts valid payloads received and stored."""

    fetched: int = Field(ge=0)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)

    @model_validator(mode="after")
    def _fetched_is_the_sum(self) -> Self:
        if self.fetched != self.created + self.updated + self.unchanged:
            raise ValueError("fetched must equal created + updated + unchanged")
        return self


class SetCounts(KindCounts):
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)


class CardCounts(KindCounts):
    failed: int = Field(ge=0)


class SyncCounts(_Model):
    series: KindCounts
    sets: SetCounts
    cards: CardCounts


class SyncResult(_Model):
    counts: SyncCounts
    failures: tuple[Failure, ...] = Field(max_length=MAX_FAILURES)


class Change(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


def classify[T](stored: T | None, fetched: T) -> Change:
    """Compare every entity field. Source and fetched-at are not entity fields."""
    if stored is None:
        return Change.CREATED
    return Change.UNCHANGED if stored == fetched else Change.UPDATED


@dataclass(frozen=True)
class SetChanges:
    """How one set's write changes the store. `series` is None when not written."""

    series: Change | None
    card_set: Change
    cards: tuple[Change, ...]


def plan_set(
    stored: StoredCatalog,
    listing: SetListing,
    cards: Sequence[Card],
    series_written: Set[str],
) -> tuple[SetBatch, SetChanges]:
    """Build one set's write and classify each row against what is stored.

    The series is written and counted only when the run first stores one of its sets.
    """
    write_series = listing.series.id not in series_written
    series_change = (
        classify(stored.series and stored.series.value, listing.series)
        if write_series
        else None
    )
    batch = SetBatch(
        series=listing.series if write_series else None,
        card_set=listing.card_set,
        cards=tuple(cards),
    )
    changes = SetChanges(
        series=series_change,
        card_set=classify(stored.card_set and stored.card_set.value, listing.card_set),
        cards=tuple(
            classify(
                stored.cards[card.id].value if card.id in stored.cards else None, card
            )
            for card in cards
        ),
    )
    return batch, changes


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

    def record(self, changes: SetChanges) -> None:
        if changes.series is not None:
            self._series[changes.series] += 1
        self._sets[changes.card_set] += 1
        self._cards.update(changes.cards)

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
