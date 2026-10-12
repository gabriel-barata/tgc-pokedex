"""Composition root of `tcg sync catalog`.

Prints the closed run as one JSON object on stdout, logs JSON lines on stderr, and
returns the exit code for the run's status. When the run record cannot be created or
closed, it prints nothing, logs `sync.run.error` and returns 2.
"""

import time
from collections.abc import Callable

import httpx2

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.service import sync_catalog
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine
from tcg_pokedex.sync_runs.adapters.postgres import PostgresSyncRunRepository
from tcg_pokedex.sync_runs.command import (
    EXIT_CODES,
    STORE_ERROR_EXIT_CODE,
    app_logger,
    json_lines_on_stderr,
)


def run_catalog_sync(
    settings: Settings,
    clock: Clock,
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one catalog sync. The app's log goes only to stderr, as JSON lines."""
    engine = create_database_engine(str(settings.database_url))
    try:
        with (
            json_lines_on_stderr(),
            TcgdexProvider(transport=transport, sleep=sleep) as provider,
        ):
            try:
                run = sync_catalog(
                    provider,
                    PostgresCatalogRepository(engine),
                    PostgresSyncRunRepository(engine),
                    clock,
                )
            except Exception as error:
                app_logger.error(
                    "sync.run.error", extra={"fields": {"error": str(error)}}
                )
                return STORE_ERROR_EXIT_CODE
        print(run.model_dump_json())
        return EXIT_CODES[run.status]
    finally:
        engine.dispose()
