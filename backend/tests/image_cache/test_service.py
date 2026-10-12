from datetime import UTC, datetime, timedelta

from tcg_pokedex.clock.fake import FakeClock
from tcg_pokedex.image_cache.domain import (
    ArtworkKind,
    CardImages,
    ImageCounts,
    ImageFailure,
    ImageSyncResult,
    Language,
    StoredCardImage,
)
from tcg_pokedex.image_cache.fakes import (
    InMemoryImageCacheRepository,
    InMemoryImageProvider,
    InMemoryImageStore,
)
from tcg_pokedex.image_cache.service import ImageSyncPorts, sync_images
from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID
from tcg_pokedex.sync_runs.domain import RunStatus, SyncRun
from tcg_pokedex.sync_runs.fakes import InMemorySyncRunRepository

START = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
LATER = START + timedelta(hours=1)
IMAGES = CardImages(small=b"small", large=b"large")
PT_001 = "https://assets.tcgdex.net/pt/sv/sv01/001"
PT_004 = "https://assets.tcgdex.net/pt/sv/sv01/004"
PT_SV02 = "https://assets.tcgdex.net/pt/sv/sv02/001"
PT_002 = "https://assets.tcgdex.net/pt/sv/sv01/002"
PT_005 = "https://assets.tcgdex.net/pt/sv/sv01/005"
EN_005 = "https://assets.tcgdex.net/en/sv/sv01/005"
SV02_LOGO = "https://assets.tcgdex.net/pt/sv/sv02/logo"
SV02_SYMBOL = "https://assets.tcgdex.net/univ/sv/sv02/symbol"
PT_IMAGES = CardImages(small=b"pt small", large=b"pt large")
EN_002 = "https://assets.tcgdex.net/en/sv/sv01/002"
SV01_LOGO = "https://assets.tcgdex.net/pt/sv/sv01/logo"
SERVER_ERROR = "HTTP 500 after 3 attempts"


class World:
    """sv01: a pt card, an English-only card, a card with no image, a failing card."""

    def __init__(self) -> None:
        self.provider = InMemoryImageProvider()
        self.provider.add_image(PT_001, IMAGES)
        self.provider.add_english("sv01-002", EN_002)
        self.provider.add_image(EN_002, IMAGES)
        self.provider.fail(PT_004, SERVER_ERROR)
        self.provider.add_artwork(SV01_LOGO, b"logo")
        self.repository = InMemoryImageCacheRepository()
        self.repository.add_set("sv01", logo_url=SV01_LOGO)
        self.repository.add_card("sv01-001", "sv01", PT_001)
        self.repository.add_card("sv01-002", "sv01", None)
        self.repository.add_card("sv01-003", "sv01", None)
        self.repository.add_card("sv01-004", "sv01", PT_004)
        self.store = InMemoryImageStore()
        self.runs = InMemorySyncRunRepository()

    def sync(
        self, at: datetime = START, set_id: str | None = "sv01"
    ) -> SyncRun[ImageSyncResult]:
        ports = ImageSyncPorts(self.provider, self.store, self.repository, self.runs)
        return sync_images(ports, FakeClock(at), set_id=set_id)


def test_a_set_run_caches_pt_then_english_and_records_the_rest() -> None:
    world = World()

    run = world.sync()

    assert set(world.store.cards) == {"sv01-001", "sv01-002"}
    assert world.repository.card_images == {
        "sv01-001": StoredCardImage(Language.PT, START),
        "sv01-002": StoredCardImage(Language.EN, START),
        "sv01-003": StoredCardImage(None, START),
    }
    assert run.status is RunStatus.PARTIAL
    assert run.result is not None
    assert run.result.set_id == "sv01"
    assert run.result.counts.cards == ImageCounts(
        downloaded=2, cached=0, unavailable=1, failed=1
    )
    assert run.result.counts.artwork == ImageCounts(
        downloaded=0, cached=0, unavailable=0, failed=0
    )
    assert run.result.failures == (
        ImageFailure(kind="card", provider_id="sv01-004", reason=SERVER_ERROR),
    )
    assert SV01_LOGO not in world.provider.requests
    assert world.runs.get_run(run.id, ImageSyncResult) == run


def test_a_second_run_skips_pt_images_and_retries_failures() -> None:
    world = World()
    world.sync()
    world.provider.requests.clear()

    run = world.sync(LATER)

    assert PT_001 not in world.provider.requests
    assert PT_004 in world.provider.requests
    assert run.result is not None
    assert run.result.counts.cards.cached == 2
    assert run.result.counts.cards.failed == 1


def test_an_unwritable_store_fails_the_run() -> None:
    world = World()
    world.store = InMemoryImageStore(writable=False)

    run = world.sync()

    assert run.status is RunStatus.FAILED
    assert run.error == "image directory is not writable"
    assert world.provider.requests == []
    assert world.runs.get_run(run.id, ImageSyncResult) == run


def test_an_unscoped_run_downloads_cards_of_tracked_sets_only() -> None:
    world = World()
    world.repository.add_set("sv02")
    world.repository.add_card("sv02-001", "sv02", PT_SV02)
    world.repository.track(HOUSEHOLD_OWNER_ID, "sv01", START)

    world.sync(set_id=None)

    assert PT_001 in world.provider.requests
    assert PT_SV02 not in world.provider.requests
    assert "en/sv02-001" not in world.provider.requests


def test_an_unscoped_run_caches_every_sets_artwork_once() -> None:
    world = World()
    world.repository.add_set("sv02", logo_url=SV02_LOGO, symbol_url=SV02_SYMBOL)
    world.provider.fail(SV02_LOGO, SERVER_ERROR)

    run = world.sync(set_id=None)
    world.provider.requests.clear()
    second = world.sync(LATER, set_id=None)

    assert world.store.artwork == {("sv01", ArtworkKind.LOGO): b"logo"}
    assert world.repository.artwork == {("sv01", ArtworkKind.LOGO): START}
    assert run.result is not None
    assert run.result.counts.artwork == ImageCounts(
        downloaded=1, cached=0, unavailable=2, failed=1
    )
    assert run.result.failures == (
        ImageFailure(kind="logo", provider_id="sv02", reason=SERVER_ERROR),
    )
    assert SV01_LOGO not in world.provider.requests
    assert second.result is not None
    assert second.result.counts.artwork.cached == 1


def test_english_images_are_replaced_once_a_pt_image_appears() -> None:
    world = World()
    world.repository.add_card("sv01-005", "sv01", PT_005)
    world.provider.add_english("sv01-005", EN_005)
    world.provider.add_image(EN_005, IMAGES)
    world.sync()
    world.repository.add_card("sv01-002", "sv01", PT_002)
    world.provider.add_image(PT_002, PT_IMAGES)
    world.provider.requests.clear()

    world.sync(LATER)

    assert world.store.cards["sv01-002"] == PT_IMAGES
    assert world.repository.card_images["sv01-002"] == StoredCardImage(
        Language.PT, LATER
    )
    assert world.repository.card_images["sv01-005"] == StoredCardImage(
        Language.EN, START
    )
    assert EN_005 not in world.provider.requests
