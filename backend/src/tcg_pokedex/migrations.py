"""Apply database migrations: `python -m tcg_pokedex.migrations`.

Upgrades the database in TCG_POKEDEX_DATABASE_URL to the latest revision. The
container entrypoint runs it before starting the app; it is a no-op when the
database is already up to date.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from tcg_pokedex.config import Settings

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config(database_url: str) -> Config:
    config = Config(ALEMBIC_INI)
    config.attributes["database_url"] = database_url
    return config


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def main() -> None:
    upgrade_to_head(str(Settings().database_url))


if __name__ == "__main__":
    main()
