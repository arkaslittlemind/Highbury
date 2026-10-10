"""Settings of the analyst service, read from the environment."""

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(Exception):
    """A required environment variable is missing or unusable."""


class Settings(BaseSettings):
    # A validation error must never repeat a value: one of them is a database URL.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    analyst_database_url: str


@lru_cache
def get_settings() -> Settings:
    """Return the settings. Raise SettingsError that names each bad variable."""
    try:
        return Settings()
    except ValidationError as error:
        names = ", ".join(str(problem["loc"][0]).upper() for problem in error.errors())
        raise SettingsError(f"{names} is not set") from None
