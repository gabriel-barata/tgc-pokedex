"""Downloading a set's images right after it is tracked."""

import threading
from pathlib import Path

import httpx2
from sqlalchemy import Engine

from tcg_pokedex.jobs.image_sync import sync_images
from tcg_pokedex.models.sync_runs import join_syncs, release_syncs
from tcg_pokedex.providers.tcgdex import Tcgdex


class DownloadRegistry:
    """The sets whose track-triggered download runs in this process. Thread-safe."""

    def __init__(self) -> None:
        self._running: set[str] = set()
        self._lock = threading.Lock()

    def start(self, set_id: str) -> bool:
        """Mark the set's download as running; False when it already was."""
        with self._lock:
            if set_id in self._running:
                return False
            self._running.add(set_id)
            return True

    def finish(self, set_id: str) -> None:
        with self._lock:
            self._running.discard(set_id)

    def is_running(self, set_id: str) -> bool:
        with self._lock:
            return set_id in self._running

    def running(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._running)


def download_set(
    engine: Engine,
    registry: DownloadRegistry,
    image_dir: Path,
    transport: httpx2.BaseTransport | None,
    set_id: str,
) -> None:
    """Download the set's images once no full sync runs; set downloads run together."""
    try:
        lock = join_syncs(engine)
        try:
            with Tcgdex(transport=transport) as tcgdex:
                sync_images(engine, tcgdex, image_dir, set_id=set_id)
        finally:
            release_syncs(lock)
    finally:
        registry.finish(set_id)
