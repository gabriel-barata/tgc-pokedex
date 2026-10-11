from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """The app's single configuration source, read from TCG_POKEDEX_* env vars.

    Unrelated keys in .env are ignored, so the file can be shared with other
    services (e.g. compose).
    """

    model_config = SettingsConfigDict(
        env_prefix="TCG_POKEDEX_", env_file=".env", extra="ignore"
    )

    environment: Literal["dev", "prod"] = "dev"
