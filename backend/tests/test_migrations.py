import runpy
import sys

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect

from tcg_pokedex.migrations import alembic_config, upgrade_to_head

SCHEMA = {
    "alembic_version",
    "owners",
    "series",
    "sets",
    "cards",
    "sync_runs",
    "tracked_sets",
    "card_images",
    "set_artwork",
}


def table_names(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_the_schema_on_an_empty_database(
    empty_database_url: str,
) -> None:
    upgrade_to_head(empty_database_url)

    assert table_names(empty_database_url) == SCHEMA


def test_upgrade_is_a_no_op_when_already_at_head(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)

    upgrade_to_head(empty_database_url)

    assert table_names(empty_database_url) == SCHEMA


def test_migrations_match_the_table_definitions(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)

    command.check(alembic_config(empty_database_url))


def test_downgrade_to_base_removes_the_schema(empty_database_url: str) -> None:
    upgrade_to_head(empty_database_url)

    command.downgrade(alembic_config(empty_database_url), "base")

    assert table_names(empty_database_url) == {"alembic_version"}


def test_module_upgrades_the_configured_database(
    monkeypatch: pytest.MonkeyPatch, empty_database_url: str
) -> None:
    monkeypatch.setenv("TCG_POKEDEX_DATABASE_URL", empty_database_url)
    monkeypatch.delitem(sys.modules, "tcg_pokedex.migrations")

    runpy.run_module("tcg_pokedex.migrations", run_name="__main__")

    assert {"owners", "cards"} <= table_names(empty_database_url)
