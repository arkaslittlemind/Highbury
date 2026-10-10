import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from psycopg import sql

from analyst.settings import get_settings
from ingest import load, migrate


@dataclass(frozen=True)
class Database:
    admin_url: str
    ingest_url: str
    analyst_url: str


def with_database(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


@pytest.fixture(scope="session")
def settings() -> tuple[str, dict[str, str]]:
    try:
        return migrate.load_settings(dict(os.environ))
    except migrate.SettingsError as error:
        pytest.fail(f"{error}. Run the tests with: uv run --env-file .env pytest")


@contextmanager
def temporary_database(admin_url: str) -> Iterator[str]:
    """Create a throwaway database so tests never touch the real one."""
    name = f"highbury_test_{uuid.uuid4().hex[:12]}"
    try:
        server = psycopg.connect(admin_url, autocommit=True)
    except psycopg.OperationalError as error:
        pytest.fail(f"Cannot reach Postgres. Run: docker compose up -d ({error})")
    with server:
        server.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            yield name
        finally:
            server.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def empty_db(settings) -> Iterator[str]:
    """Admin URL of a fresh database with nothing in it."""
    admin_url, _ = settings
    with temporary_database(admin_url) as name:
        yield with_database(admin_url, name)


@pytest.fixture
def ingest(db) -> Iterator[psycopg.Connection]:
    """A connection as the ingest role that leaves the shared database empty."""
    with psycopg.connect(db.ingest_url) as conn:
        yield conn
        conn.rollback()
        # Some tests commit so that analyst_ro can read the rows. The database is
        # shared by the whole session, so every test that loads data empties it.
        conn.execute(
            sql.SQL("TRUNCATE {}").format(
                sql.SQL(", ").join(map(sql.Identifier, (*load.SEASON_TABLES, "data_catalog")))
            )
        )


@pytest.fixture
def analyst(db) -> Iterator[psycopg.Connection]:
    with psycopg.connect(db.analyst_url, autocommit=True) as conn:
        yield conn


@pytest.fixture(scope="session")
def db(settings) -> Iterator[Database]:
    """A fresh database with every migration applied."""
    admin_url, passwords = settings
    with temporary_database(admin_url) as name:
        migrate.apply(with_database(admin_url, name), passwords)
        yield Database(
            admin_url=with_database(admin_url, name),
            ingest_url=with_database(os.environ["INGEST_DATABASE_URL"], name),
            analyst_url=with_database(os.environ["ANALYST_DATABASE_URL"], name),
        )


@pytest.fixture
def analyst_url(monkeypatch) -> Iterator[Callable[[str | None], None]]:
    """Set the database URL that the analyst service reads, for one test."""

    def use(url: str | None) -> None:
        if url is None:
            monkeypatch.delenv("ANALYST_DATABASE_URL", raising=False)
        else:
            monkeypatch.setenv("ANALYST_DATABASE_URL", url)
        # The settings are read one time and kept, so drop the kept ones.
        get_settings.cache_clear()

    yield use
    get_settings.cache_clear()


@pytest.fixture
def analyst_env(db, analyst_url) -> Database:
    """Point the analyst service at the test database."""
    analyst_url(db.analyst_url)
    return db
