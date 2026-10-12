"""Composition root of `tcg sync catalog`."""

import time
from collections.abc import Callable
from functools import partial

import httpx2

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.service import sync_catalog
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.command import report_run


def run_catalog_sync(
    settings: Settings,
    clock: Clock,
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one catalog sync and return its exit code (see `report_run`)."""
    engine = create_database_engine(str(settings.database_url))
    try:
        with TcgdexProvider(transport=transport, sleep=sleep) as provider:
            return report_run(
                partial(
                    sync_catalog,
                    provider,
                    PostgresCatalogRepository(engine),
                    PostgresSyncRunRepository(engine),
                    clock,
                )
            )
    finally:
        engine.dispose()
