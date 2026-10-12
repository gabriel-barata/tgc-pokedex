"""The `tcg` console command: `tcg sync catalog` and `tcg sync images`."""

import argparse
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import NoReturn

import httpx2

from tcg_pokedex.config import Settings
from tcg_pokedex.db import create_database_engine
from tcg_pokedex.services.catalog_sync import sync_catalog
from tcg_pokedex.services.image_sync import sync_images
from tcg_pokedex.services.sync_runs import report_run
from tcg_pokedex.tcgdex import Tcgdex


def run_sync(
    target: str,
    settings: Settings,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    transport: httpx2.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run the `catalog` or `images` sync; return its exit code (see `report_run`)."""
    engine = create_database_engine(str(settings.database_url))
    try:
        with Tcgdex(transport=transport, sleep=sleep) as tcgdex:
            if target == "images":
                return report_run(
                    lambda: sync_images(engine, tcgdex, settings.image_dir, now=now)
                )
            return report_run(lambda: sync_catalog(engine, tcgdex, now))
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
    return parser


def main(argv: Sequence[str] | None = None) -> NoReturn:
    raise SystemExit(run_sync(_parser().parse_args(argv).target, Settings()))
