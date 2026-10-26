"""Settings of the analyst service, read from the environment."""

import math
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

INPUT_PRICE = "ANALYST_INPUT_USD_PER_MTOK"
OUTPUT_PRICE = "ANALYST_OUTPUT_USD_PER_MTOK"


class SettingsError(Exception):
    """A required environment variable is missing or unusable."""


class Settings(BaseSettings):
    # A validation error must never repeat a value: one of them is a database URL.
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    analyst_database_url: str
    # Only the agent needs a model. The MCP server starts without one.
    analyst_model: str | None = None
    # Only the API needs these four, so they are text here and api_settings
    # checks them. The command line and the MCP server start without them.
    cors_origins: str | None = None
    rate_limit_per_minute: str | None = None
    analyst_input_usd_per_mtok: str | None = None
    analyst_output_usd_per_mtok: str | None = None


class ApiSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    cors_origins: tuple[str, ...]
    rate_limit_per_minute: int
    # US dollars for one million tokens. None when the price is not known.
    input_usd_per_mtok: float | None
    output_usd_per_mtok: float | None


@lru_cache
def get_settings() -> Settings:
    """Return the settings. Raise SettingsError that names each bad variable."""
    try:
        return Settings()
    except ValidationError as error:
        names = ", ".join(str(problem["loc"][0]).upper() for problem in error.errors())
        raise SettingsError(f"{names} is not set") from None


def model_name() -> str:
    """Return the init_chat_model name of the agent's model. Raise SettingsError if none."""
    name = (get_settings().analyst_model or "").strip()
    if not name:
        raise SettingsError("ANALYST_MODEL is not set")
    return name


def origins(text: str) -> tuple[str, ...] | None:
    """Return the origins of a comma-separated text, or None when one is not an origin."""
    found = tuple(part.strip() for part in text.split(","))
    for origin in found:
        try:
            parts = urlsplit(origin)
        except ValueError:
            # A broken IPv6 address, for example "http://[::1".
            return None
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return None
        # A browser sends an origin in lower case with no path, and CORS compares
        # the full text. Any other form never matches, and the start shows no sign.
        if " " in origin or origin != f"{parts.scheme}://{parts.netloc}".lower():
            return None
    return found


def whole_number(text: str) -> int | None:
    """Return the whole number, 1 or more, or None."""
    return int(text) if text.isascii() and text.isdigit() and int(text) >= 1 else None


def price(text: str) -> float | None:
    """Return the price, 0 or more, or None."""
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def api_settings() -> ApiSettings:
    """Return the settings that only the API reads. Raise SettingsError that names each
    bad variable and repeats no value."""
    settings = get_settings()
    parsers = {
        "CORS_ORIGINS": origins,
        "RATE_LIMIT_PER_MINUTE": whole_number,
        INPUT_PRICE: price,
        OUTPUT_PRICE: price,
    }
    # A blank value is the same as no value.
    texts = {name: (getattr(settings, name.lower()) or "").strip() for name in parsers}
    values = {name: parsers[name](text) if text else None for name, text in texts.items()}
    required = {"CORS_ORIGINS", "RATE_LIMIT_PER_MINUTE"}
    if texts[INPUT_PRICE] or texts[OUTPUT_PRICE]:
        # One price with no second price gives a cost that is too low, with no sign of it.
        required |= {INPUT_PRICE, OUTPUT_PRICE}
    problems = []
    for name, text in texts.items():
        if not text and name in required:
            problems.append(f"{name} is not set")
        elif text and values[name] is None:
            problems.append(f"{name} is not valid")
    if problems:
        raise SettingsError(", ".join(problems))
    return ApiSettings(
        cors_origins=values["CORS_ORIGINS"],
        rate_limit_per_minute=values["RATE_LIMIT_PER_MINUTE"],
        input_usd_per_mtok=values[INPUT_PRICE],
        output_usd_per_mtok=values[OUTPUT_PRICE],
    )
