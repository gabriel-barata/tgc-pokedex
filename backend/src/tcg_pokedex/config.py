from typing import Literal

from pydantic import DirectoryPath, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The app's single configuration source, read from TCG_POKEDEX_* env vars.

    Unrelated keys in .env are ignored, so the file can be shared with other
    services (e.g. compose). database_url defaults to the throwaway local
    database from compose.dev.yml; every other environment sets it. spa_dir is
    the built frontend the app serves; it stays unset in dev, where Vite serves it.
    """

    model_config = SettingsConfigDict(
        env_prefix="TCG_POKEDEX_", env_file=".env", extra="ignore"
    )

    environment: Literal["dev", "prod"] = "dev"
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://tcg_pokedex:tcg_pokedex@localhost:5432/tcg_pokedex"
    )
    spa_dir: DirectoryPath | None = None
