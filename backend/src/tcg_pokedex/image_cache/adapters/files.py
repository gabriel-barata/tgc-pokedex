import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from tcg_pokedex.image_cache.domain import ArtworkKind, CardImages, CardSize
from tcg_pokedex.image_cache.ports import ImageStoreUnavailableError

SUFFIX = ".webp"


class FileImageStore:
    """ImageStore on a directory.

    Layout: `cards/{card_id}/{size}.webp` and `sets/{set_id}/{kind}.webp`.
    Ids are percent-encoded, and `.` and `..` never name a file. Each file is written
    to a temporary file beside it, synced, then moved into place.
    """

    def __init__(self, image_dir: Path) -> None:
        self._root = image_dir

    def check_writable(self) -> None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=self._root):
                pass
        except OSError as error:
            raise ImageStoreUnavailableError(
                f"image directory {self._root} is not writable: {error.strerror}"
            ) from error

    def has_card(self, card_id: str) -> bool:
        return all(self.card_path(card_id, size) for size in CardSize)

    def put_card(self, card_id: str, images: CardImages) -> None:
        folder = self._folder("cards", card_id)
        _write(folder, CardSize.SMALL, images.small)
        _write(folder, CardSize.LARGE, images.large)

    def put_artwork(self, set_id: str, kind: ArtworkKind, content: bytes) -> None:
        _write(self._folder("sets", set_id), kind, content)

    def card_path(self, card_id: str, size: CardSize) -> Path | None:
        """The stored file, or None when it is absent or the id is invalid."""
        return self._existing("cards", card_id, size)

    def artwork_path(self, set_id: str, kind: ArtworkKind) -> Path | None:
        return self._existing("sets", set_id, kind)

    def _existing(self, area: str, item_id: str, name: str) -> Path | None:
        if item_id in {".", ".."}:
            return None
        path = self._folder(area, item_id) / f"{name}{SUFFIX}"
        return path if path.is_file() else None

    def _folder(self, area: str, item_id: str) -> Path:
        if item_id in {".", ".."}:
            raise ValueError(f"invalid id {item_id!r}")
        return self._root / area / quote(item_id, safe="")


def _write(folder: Path, name: str, content: bytes) -> None:
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
