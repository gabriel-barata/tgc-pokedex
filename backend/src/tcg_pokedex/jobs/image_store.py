"""Cached card images and set artwork on disk.

Files live under the image directory as `cards/{card_id}/{size}.webp` and
`sets/{set_id}/{kind}.webp`. Ids are percent-encoded, and `.` and `..` never name a
file. Each file is written to a temporary file beside it, synced, then moved into place.
"""

import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from tcg_pokedex.views.images import ArtworkKind, CardSize

SUFFIX = ".webp"


class ImageStoreUnavailableError(Exception):
    """The image directory cannot be created or written, so no run can go on."""


def card_path(image_dir: Path, card_id: str, size: CardSize) -> Path | None:
    """The stored file, or None when it is absent or the id is invalid."""
    return _existing(image_dir, "cards", card_id, size)


def artwork_path(image_dir: Path, set_id: str, kind: ArtworkKind) -> Path | None:
    return _existing(image_dir, "sets", set_id, kind)


def _existing(image_dir: Path, area: str, item_id: str, name: str) -> Path | None:
    if item_id in {".", ".."}:
        return None
    path = item_folder(image_dir, area, item_id) / f"{name}{SUFFIX}"
    return path if path.is_file() else None


def item_folder(image_dir: Path, area: str, item_id: str) -> Path:
    if item_id in {".", ".."}:
        raise ValueError(f"invalid id {item_id!r}")
    return image_dir / area / quote(item_id, safe="")


def write_file(folder: Path, name: str, content: bytes) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, folder / f"{name}{SUFFIX}")
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def check_writable(image_dir: Path) -> None:
    try:
        image_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=image_dir):
            pass
    except OSError as error:
        raise ImageStoreUnavailableError(
            f"image directory {image_dir} is not writable: {error.strerror}"
        ) from error
