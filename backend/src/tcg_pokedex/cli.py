"""The `tcg` console command: `tcg sync catalog`."""

import argparse
from collections.abc import Sequence
from typing import NoReturn

from tcg_pokedex.catalog_sync.command import run_catalog_sync
from tcg_pokedex.clock.adapters.system import SystemClock
from tcg_pokedex.config import Settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tcg", description="TCG Pokédex tasks.")
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="copy provider data into our store")
    targets = sync.add_subparsers(dest="target", required=True)
    targets.add_parser(
        "catalog",
        help="copy the TCGdex pt catalog (exit 0 succeeded, 1 partial, 2 failed)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> NoReturn:
    _parser().parse_args(argv)
    raise SystemExit(run_catalog_sync(Settings(), SystemClock()))
