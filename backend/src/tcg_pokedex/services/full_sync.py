"""`tcg sync all`, the worker's schedule and "Sincronizar agora": the catalog, then
the images."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine

from tcg_pokedex.schemas import RunStatus
from tcg_pokedex.services.catalog_sync import sync_catalog
from tcg_pokedex.services.image_sync import sync_images
from tcg_pokedex.services.sync_runs import SyncRun
from tcg_pokedex.tcgdex import Tcgdex


def sync_all(
    engine: Engine,
    tcgdex: Tcgdex,
    image_dir: Path,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[SyncRun[Any]]:
    """Sync the catalog, then the images unless the catalog run failed."""
    catalog = sync_catalog(engine, tcgdex, now)
    if catalog.status is RunStatus.FAILED:
        return [catalog]
    return [catalog, sync_images(engine, tcgdex, image_dir, now=now)]
