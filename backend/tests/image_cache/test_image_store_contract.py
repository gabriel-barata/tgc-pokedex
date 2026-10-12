"""Contract every ImageStore must honour, run on the fake and the file store.

The file-only cases below cover what only the real adapter has: paths and atomic writes.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from tcg_pokedex.image_cache.adapters.files import FileImageStore
from tcg_pokedex.image_cache.domain import ArtworkKind, CardImages, CardSize
from tcg_pokedex.image_cache.fakes import InMemoryImageStore
from tcg_pokedex.image_cache.ports import ImageStore, ImageStoreUnavailableError

IMAGES = CardImages(small=b"small", large=b"large")


def make_fake_store(_tmp_path: Path, writable: bool) -> ImageStore:
    return InMemoryImageStore(writable=writable)


def make_file_store(tmp_path: Path, writable: bool) -> ImageStore:
    if writable:
        return FileImageStore(tmp_path / "images")
    read_only = tmp_path / "read-only"
    read_only.mkdir(mode=0o500)
    return FileImageStore(read_only / "images")


@pytest.fixture(params=[make_fake_store, make_file_store], ids=["fake", "file"])
def make_store(request: pytest.FixtureRequest) -> Callable[[Path, bool], ImageStore]:
    factory: Callable[[Path, bool], ImageStore] = request.param
    return factory


def test_a_stored_card_has_both_sizes(
    make_store: Callable[[Path, bool], ImageStore], tmp_path: Path
) -> None:
    store = make_store(tmp_path, True)
    store.check_writable()

    store.put_card("sv01-001", IMAGES)

    assert store.has_card("sv01-001")
    assert not store.has_card("sv01-002")


def test_an_unwritable_store_raises(
    make_store: Callable[[Path, bool], ImageStore], tmp_path: Path
) -> None:
    store = make_store(tmp_path, False)

    with pytest.raises(ImageStoreUnavailableError):
        store.check_writable()


@pytest.fixture
def files(tmp_path: Path) -> FileImageStore:
    store = FileImageStore(tmp_path / "images")
    store.check_writable()
    return store


def test_stored_files_are_served_by_path(files: FileImageStore) -> None:
    files.put_card("sv01-001", IMAGES)
    files.put_artwork("sv01", ArtworkKind.LOGO, b"logo")

    small = files.card_path("sv01-001", CardSize.SMALL)
    large = files.card_path("sv01-001", CardSize.LARGE)
    logo = files.artwork_path("sv01", ArtworkKind.LOGO)
    assert small is not None
    assert large is not None
    assert logo is not None
    assert (small.read_bytes(), large.read_bytes()) == (b"small", b"large")
    assert logo.read_bytes() == b"logo"
    assert files.artwork_path("sv01", ArtworkKind.SYMBOL) is None
    assert files.card_path("sv01-002", CardSize.SMALL) is None


def test_a_card_with_one_size_is_not_stored(files: FileImageStore) -> None:
    files.put_card("sv01-001", IMAGES)
    large = files.card_path("sv01-001", CardSize.LARGE)
    assert large is not None

    large.unlink()

    assert not files.has_card("sv01-001")


def test_ids_cannot_leave_the_image_directory(
    files: FileImageStore, tmp_path: Path
) -> None:
    files.put_card("a/../../b", IMAGES)

    path = files.card_path("a/../../b", CardSize.SMALL)
    assert path is not None
    assert path.resolve().is_relative_to((tmp_path / "images").resolve())
    assert files.card_path("..", CardSize.SMALL) is None
    assert files.card_path(".", CardSize.SMALL) is None


def test_a_failed_write_leaves_no_file(
    files: FileImageStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def failing_replace(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="disk full"):
        files.put_artwork("sv01", ArtworkKind.LOGO, b"logo")

    assert files.artwork_path("sv01", ArtworkKind.LOGO) is None
    assert [p for p in (tmp_path / "images").rglob("*") if p.is_file()] == []
