"""The one read path to the database, as the analyst_ro role."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import psycopg

from analyst.settings import get_settings

# Without a limit, an unreachable database makes a tool call wait with no end.
CONNECT_TIMEOUT_SECONDS = 10

UNREACHABLE = "The database is not reachable."


class DatabaseUnavailable(Exception):
    """The database cannot be reached."""


class QueryTimeout(Exception):
    """The statement ran longer than its timeout and the server stopped it."""


class QueryFailed(Exception):
    """The statement did not run. The text is safe to show: it holds no URL."""


@dataclass(frozen=True)
class Rows:
    columns: list[str]
    rows: list[tuple[Any, ...]]


def read(sql: str, timeout_ms: int, params: Sequence[Any] | None = None) -> Rows:
    """Run one statement in a read-only transaction and return its rows.

    This is the database lock. It must hold for any SQL text, also when the SQL
    guard is not in front of it.
    """
    if "\x00" in sql:
        # The client library ends the text at a NUL, so the server would get a
        # different statement from the one the caller has.
        raise QueryFailed("The SQL has a NUL character.")

    url = get_settings().analyst_database_url
    try:
        # One connection for one call: a setting that this statement changes for
        # its session cannot reach the next call.
        conn = psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS)
    except psycopg.Error:
        # The text of a client-side error can repeat the URL, password included.
        raise DatabaseUnavailable(UNREACHABLE) from None

    try:
        # The role has a read-only default and a timeout, but a session can change
        # its own defaults. Thus each transaction states the two again.
        conn.read_only = True
        # In pipeline mode psycopg uses the extended protocol only, and that
        # protocol refuses a string with more than one statement. A % in the SQL
        # stays literal when no parameters go with it.
        with conn.pipeline():
            conn.execute("SELECT set_config('statement_timeout', %s, true)", (str(timeout_ms),))
            cur = conn.execute(sql, params)
        columns = [column.name for column in cur.description or ()]
        return Rows(columns, cur.fetchall() if cur.description else [])
    except psycopg.errors.QueryCanceled:
        raise QueryTimeout() from None
    except psycopg.Error as error:
        if error.sqlstate is None and isinstance(error, psycopg.OperationalError):
            # No answer from the server: the connection is gone.
            raise DatabaseUnavailable(UNREACHABLE) from None
        raise QueryFailed(error.diag.message_primary or type(error).__name__) from None
    except UnicodeEncodeError:
        raise QueryFailed("The SQL has a character that the database cannot read.") from None
    finally:
        # A close with no commit ends the transaction, so nothing can stay.
        conn.close()
