from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from tcg_pokedex.database import MIGRATIONS_DIR, migrate
from tcg_pokedex.models.owner import HOUSEHOLD_OWNER_ID, HOUSEHOLD_OWNER_NAME

TABLES = {
    "owners",
    "series",
    "sets",
    "cards",
    "sync_runs",
    "tracked_sets",
    "card_images",
    "set_artwork",
    "ownership",
}


def read_database(database_url: str) -> tuple[set[str], list[tuple[object, ...]]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            owners = connection.execute(text("SELECT id, name FROM owners")).all()
        return set(inspect(engine).get_table_names()), [tuple(row) for row in owners]
    finally:
        engine.dispose()


def test_migrate_builds_the_schema_and_seeds_the_household_owner(
    empty_database_url: str,
) -> None:
    migrate(empty_database_url)
    migrate(empty_database_url)

    tables, owners = read_database(empty_database_url)
    assert tables >= TABLES
    assert owners == [(HOUSEHOLD_OWNER_ID, HOUSEHOLD_OWNER_NAME)]


def test_migrate_baselines_a_database_alembic_built_and_keeps_its_data(
    empty_database_url: str,
) -> None:
    baseline = next(Path(MIGRATIONS_DIR).glob("*_baseline.sql")).read_text()
    engine = create_engine(empty_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(baseline)
        connection.execute(text("CREATE TABLE alembic_version (version_num text)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0004')"))
        connection.execute(
            text(
                "INSERT INTO series (id, name, source, fetched_at)"
                " VALUES ('sv', 'Escarlate e Violeta', 'tcgdex', now())"
            )
        )

    migrate(empty_database_url)

    with engine.connect() as connection:
        series = connection.execute(text("SELECT id FROM series")).all()
        revisions = connection.execute(
            text("SELECT count(*) FROM atlas_schema_revisions")
        ).scalar_one()
    engine.dispose()
    assert [tuple(row) for row in series] == [("sv",)]
    assert revisions == 1
