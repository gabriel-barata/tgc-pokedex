from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

type Environment = Literal["dev", "prod"]


class Settings(BaseSettings):
    """The app's single configuration source, read from TCG_POKEDEX_* env vars."""

    # extra="ignore": .env may also hold keys for other services (e.g. compose).
    model_config = SettingsConfigDict(
        env_prefix="TCG_POKEDEX_", env_file=".env", extra="ignore"
    )

    environment: Environment = "dev"
