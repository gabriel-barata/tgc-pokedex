"""Composition root of `tcg sync catalog`.

Prints the closed run as one JSON object on stdout, logs JSON lines on stderr, and
returns the exit code for the run's status.
"""

import json
import logging
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx2

from tcg_pokedex.catalog_sync.adapters.postgres import PostgresCatalogRepository
from tcg_pokedex.catalog_sync.adapters.tcgdex import TcgdexProvider
from tcg_pokedex.catalog_sync.domain import RunStatus
from tcg_pokedex.catalog_sync.service import sync_catalog
from tcg_pokedex.clock.ports import Clock
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine

EXIT_CODES = {RunStatus.SUCCEEDED: 0, RunStatus.PARTIAL: 1, RunStatus.FAILED: 2}

app_logger = logging.getLogger("tcg_pokedex")


class JsonLineFormatter(logging.Formatter):
    """One JSON object per record: `event`, `level`, `time` and the record's fields."""

    def format(self, record: logging.LogRecord) -> str:
        fields: dict[str, object] = record.__dict__.get("fields", {})
        return json.dumps(
            {
                "event": record.getMessage(),
                "level": record.levelname,
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
                **fields,
            },
            ensure_ascii=False,
        )


def run_catalog_sync(
    settings: Settings,
    clock: Clock,
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one catalog sync. The app's log goes only to stderr, as JSON lines."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonLineFormatter())
    previous_level, previous_propagate = app_logger.level, app_logger.propagate
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    engine = create_database_engine(str(settings.database_url))
    try:
        with TcgdexProvider(transport=transport, sleep=sleep) as provider:
            run = sync_catalog(provider, PostgresCatalogRepository(engine), clock)
        print(run.model_dump_json())
        return EXIT_CODES[run.status]
    finally:
        engine.dispose()
        app_logger.removeHandler(handler)
        app_logger.setLevel(previous_level)
        app_logger.propagate = previous_propagate
