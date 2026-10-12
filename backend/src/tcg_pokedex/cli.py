"""The `tcg` console command: `sync catalog|images|all`, `migrate` and `openapi`."""

import argparse
import json
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, NoReturn

import httpx2

from tcg_pokedex.app import create_app
from tcg_pokedex.config import Settings
from tcg_pokedex.database import create_database_engine, migrate
from tcg_pokedex.jobs.catalog_sync import sync_catalog
from tcg_pokedex.jobs.full_sync import sync_all
from tcg_pokedex.jobs.image_sync import sync_images
from tcg_pokedex.jobs.runs import SyncBusyError, report_runs
from tcg_pokedex.models.sync_runs import claim_syncs, release_syncs
from tcg_pokedex.providers.tcgdex import Tcgdex
from tcg_pokedex.views.sync import SyncRun


def run_sync(
    target: str,
    settings: Settings,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run the `catalog`, `images` or `all` sync while no other sync runs; return its
    exit code (see `report_runs`)."""
    engine = create_database_engine(str(settings.database_url))

    def sync() -> list[SyncRun[Any]]:
        lock = claim_syncs(engine)
        if lock is None:
            raise SyncBusyError("another sync is running")
        try:
            with Tcgdex(transport=transport, sleep=sleep) as tcgdex:
                if target == "catalog":
                    return [sync_catalog(engine, tcgdex, now)]
                if target == "images":
                    return [sync_images(engine, tcgdex, settings.image_dir, now=now)]
                return sync_all(engine, tcgdex, settings.image_dir, now)
        finally:
            release_syncs(lock)

    try:
        return report_runs(sync)
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tcg", description="TCG Pokédex tasks.")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="copy provider data into our store")
    targets = sync.add_subparsers(dest="target", required=True)
    targets.add_parser(
        "catalog",
        help="copy the TCGdex pt catalog (exit 0 succeeded, 1 partial, 2 failed)",
    )
    targets.add_parser(
        "images",
        help=(
            "cache tracked sets' card images and every set's logo and symbol "
            "(exit 0 succeeded, 1 partial, 2 failed)"
        ),
    )
    targets.add_parser(
        "all",
        help=(
            "sync the catalog, then the images unless the catalog run failed "
            "(exit code of the worse run)"
        ),
    )
    commands.add_parser("migrate", help="apply the database migrations")
    commands.add_parser("openapi", help="print the API's OpenAPI schema as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> NoReturn:
    arguments = _parser().parse_args(argv)
    settings = Settings()
    if arguments.command == "migrate":
        migrate(str(settings.database_url))
        raise SystemExit(0)
    if arguments.command == "openapi":
        print(json.dumps(create_app(settings).openapi(), indent=2, ensure_ascii=False))
        raise SystemExit(0)
    raise SystemExit(run_sync(arguments.target, settings))
