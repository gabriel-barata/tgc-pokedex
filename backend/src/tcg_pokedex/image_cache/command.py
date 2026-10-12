"""Composition root of `tcg sync images`."""

import time
from collections.abc import Callable
from functools import partial

import httpx2

from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.image_cache.adapters.files import FileImageStore
from tcg_pokedex.image_cache.adapters.postgres import PostgresImageCacheRepository
from tcg_pokedex.image_cache.adapters.tcgdex import TcgdexImageProvider
from tcg_pokedex.image_cache.service import ImageSyncPorts, sync_images
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.command import report_run


def run_image_sync(
    settings: Settings,
    clock: Clock,
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Catch up every tracked set and all set artwork; return the exit code."""
    engine = create_database_engine(str(settings.database_url))
    try:
        with TcgdexImageProvider(transport=transport, sleep=sleep) as provider:
            ports = ImageSyncPorts(
                provider=provider,
                store=FileImageStore(settings.image_dir),
                repository=PostgresImageCacheRepository(engine),
                runs=PostgresSyncRunRepository(engine),
            )
            return report_run(partial(sync_images, ports, clock))
    finally:
        engine.dispose()
