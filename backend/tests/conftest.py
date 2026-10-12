from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, make_url, text
from testcontainers.community.postgres import PostgresContainer

from tcg_pokedex.database import create_database_engine, migrate


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """URL of a real Postgres 17 server, started once per test session."""
    with PostgresContainer("postgres:17", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def empty_database_url(postgres_url: str) -> Iterator[str]:
    """URL of a freshly created, empty database, dropped after the test."""
    name = f"test_{uuid4().hex}"
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield (
            make_url(postgres_url)
            .set(database=name)
            .render_as_string(hide_password=False)
        )
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def database_url(empty_database_url: str) -> str:
    """URL of a fresh database migrated to the latest revision."""
    migrate(empty_database_url)
    return empty_database_url


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_database_engine(database_url)
    yield engine
    engine.dispose()
