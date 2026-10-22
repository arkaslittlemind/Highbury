"""The parts that every season command shares: raw cache, transaction, error lines."""

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import psycopg

from ingest import load
from ingest.migrate import SettingsError

# Without a limit, an unreachable database makes a command wait with no end.
CONNECT_TIMEOUT_SECONDS = 10


class FetchError(Exception):
    """A raw file could not be downloaded."""


def cached_text(path: Path, fetch: Callable[[], str], encoding: str = "utf-8") -> str:
    """Return the text in the cache file, downloading it first when it is absent."""
    if not path.exists():
        try:
            text = fetch()
        except (OSError, ValueError) as error:
            raise FetchError(f"cannot download {path.stem}: {type(error).__name__}") from error
        path.parent.mkdir(parents=True, exist_ok=True)
        # A rename is atomic, so an interrupted download never looks cached.
        partial = path.with_suffix(".tmp")
        # newline="" keeps the line ends of the download as they are, on Windows too.
        partial.write_text(text, encoding=encoding, newline="")
        partial.replace(path)
    return path.read_text(encoding=encoding)


def cached_json(path: Path, fetch: Callable[[], Any]) -> Any:
    """Return the JSON in the cache file, downloading it first when it is absent."""
    return json.loads(cached_text(path, lambda: json.dumps(fetch())))


def load_season(url: str, rows: load.SeasonRows, facts: load.SeasonFacts) -> dict[str, int]:
    """Load and check one season in one transaction. Return the table row counts."""
    # The connection block commits on a clean exit and rolls back on an error, so a
    # season that fails the check never reaches the database.
    with psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS) as conn:
        load.load(conn, rows)
        load.check_season(conn, facts)
        return load.table_counts(conn)


def execute(task: Callable[[str], list[str]], env: Mapping[str, str] = os.environ) -> int:
    """Run one load task and return its exit code.

    task gets the ingest URL and returns the lines to print. Each failure that a
    loader can expect becomes one line on stderr, with no traceback.
    """
    try:
        lines = task(load.ingest_url(env))
    except SettingsError as error:
        print(f"Settings error: {error}", file=sys.stderr)
        return 1
    except FetchError as error:
        print(f"Download failed: {error}", file=sys.stderr)
        return 1
    except load.SanityError as error:
        print(f"Sanity check failed, nothing was loaded: {error}", file=sys.stderr)
        return 1
    except (LookupError, ValueError, TypeError, AttributeError) as error:
        # A record that does not have the expected shape or values: an absent key, an
        # unknown value, a null where a number must be, a list where an object must be.
        print(
            f"Unexpected source data, nothing was loaded: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    except OSError as error:
        print(f"Cannot read or write the raw cache: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        # The text of a client-side error can repeat the URL, password included, so
        # only the server's own message is printed.
        message = error.diag.message_primary or type(error).__name__
        print(f"Load failed, nothing was loaded: {message}", file=sys.stderr)
        return 1

    for line in lines:
        print(line)
    return 0


def season_lines(counts: dict[str, int], facts: load.SeasonFacts) -> list[str]:
    return [
        *(f"{table}: {count}" for table, count in counts.items()),
        f"{facts.season} {facts.team}: {facts.matches} matches,"
        f" {facts.wins} W {facts.draws} D {facts.losses} L, {facts.points} points,"
        f" {facts.goals_for} goals for,"
        f" {facts.top_scorer} {facts.top_scorer_goals} goals",
    ]


def run(
    build: Callable[[], load.SeasonRows],
    facts: load.SeasonFacts,
    env: Mapping[str, str] = os.environ,
) -> int:
    """Run one season command and return its exit code.

    build fetches and transforms the season. It ends before the database connection
    opens, so a download or a bad record never leaves a transaction open.
    """
    return execute(lambda url: season_lines(load_season(url, build(), facts), facts), env)
