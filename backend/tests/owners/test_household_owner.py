from sqlalchemy import create_engine, select

from tcg_pokedex.migrations import upgrade_to_head
from tcg_pokedex.owners.adapters.tables import owners
from tcg_pokedex.owners.domain import HOUSEHOLD_OWNER_ID, HOUSEHOLD_OWNER_NAME


def test_migrations_seed_exactly_the_household_owner(
    empty_database_url: str,
) -> None:
    upgrade_to_head(empty_database_url)

    engine = create_engine(empty_database_url)
    with engine.connect() as connection:
        rows = connection.execute(select(owners.c.id, owners.c.name)).all()
    engine.dispose()

    assert [tuple(row) for row in rows] == [(HOUSEHOLD_OWNER_ID, HOUSEHOLD_OWNER_NAME)]
