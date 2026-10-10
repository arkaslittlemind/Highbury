"""Apply the SQL migrations in db/migrations to the database.

Run from the repository root:
    uv run --env-file .env python -m ingest.migrate
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg
from psycopg import sql

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "db" / "migrations"
MIGRATION_NAME = re.compile(r"^\d{4}_.+\.sql$")

ADMIN_URL_VAR = "DATABASE_ADMIN_URL"
ROLE_URL_VARS = {"ingest": "INGEST_DATABASE_URL", "analyst_ro": "ANALYST_DATABASE_URL"}


class SettingsError(Exception):
    """A required environment variable is missing or unusable."""


def migration_files(directory: Path) -> list[Path]:
    """Return the migration files in the order they must be applied."""
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and MIGRATION_NAME.match(p.name)),
        key=lambda p: p.name,
    )


def pending(files: list[Path], applied: set[str]) -> list[Path]:
    return [f for f in files if f.name not in applied]


def password_from_url(url: str) -> str:
    password = urlsplit(url).password
    if not password:
        raise SettingsError("the URL has no password")
    return unquote(password)


def load_settings(env: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Return the admin URL and the password for each role, read from env."""
    admin_url = env.get(ADMIN_URL_VAR)
    if not admin_url:
        raise SettingsError(f"{ADMIN_URL_VAR} is not set")

    passwords = {}
    for role, var in ROLE_URL_VARS.items():
        url = env.get(var)
        if not url:
            raise SettingsError(f"{var} is not set")
        try:
            passwords[role] = password_from_url(url)
        except SettingsError as error:
            raise SettingsError(f"{var}: {error}") from None
    return admin_url, passwords


def apply(
    admin_url: str,
    role_passwords: dict[str, str],
    directory: Path = MIGRATIONS_DIR,
) -> list[str]:
    """Apply every pending migration, then set the role passwords.

    Each file runs in its own transaction, so a failing file leaves nothing behind.
    Returns the names of the files applied in this run.
    """
    done = []
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

        for file in pending(migration_files(directory), applied):
            with conn.transaction():
                conn.execute(file.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (file.name,))
            done.append(file.name)

        for role, password in role_passwords.items():
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
    return done


def main() -> int:
    try:
        admin_url, passwords = load_settings(dict(os.environ))
        done = apply(admin_url, passwords, MIGRATIONS_DIR)
    except SettingsError as error:
        print(f"Settings error: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        print(f"Migration failed: {error}", file=sys.stderr)
        return 1

    for name in done:
        print(f"Applied {name}")
    if not done:
        print("Nothing to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
