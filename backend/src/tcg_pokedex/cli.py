"""The `tcg` console command: `tcg sync catalog` and `tcg sync images`."""

import argparse
from collections.abc import Sequence
from typing import NoReturn

from tcg_pokedex.catalog_sync.command import run_catalog_sync
from tcg_pokedex.clock.adapters.system import SystemClock
from tcg_pokedex.config import Settings
from tcg_pokedex.image_cache.command import run_image_sync


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
    target: str = _parser().parse_args(argv).target
    run = run_image_sync if target == "images" else run_catalog_sync
    raise SystemExit(run(Settings(), SystemClock()))
