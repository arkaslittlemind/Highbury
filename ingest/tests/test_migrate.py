import psycopg
import pytest

from ingest import migrate

TABLES = {
    "seasons",
    "teams",
    "players",
    "player_aliases",
    "matches",
    "shots",
    "events",
    "player_match_stats",
    "team_match_stats",
    "data_catalog",
}

ENV = {
    "DATABASE_ADMIN_URL": "postgresql://postgres:admin@localhost:5433/highbury",
    "INGEST_DATABASE_URL": "postgresql://ingest:ingest_pw@localhost:5433/highbury",
    "ANALYST_DATABASE_URL": "postgresql://analyst_ro:analyst_pw@localhost:5433/highbury",
}


def public_tables(url: str) -> set[str]:
    with psycopg.connect(url) as conn:
        rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {row[0] for row in rows}


def test_migration_files_are_ordered_and_filtered(tmp_path):
    for name in ["0010_later.sql", "0002_second.sql", "0001_first.sql", "notes.md", "draft.sql"]:
        (tmp_path / name).write_text("SELECT 1;")
    (tmp_path / "0003_dir.sql").mkdir()

    names = [f.name for f in migrate.migration_files(tmp_path)]

    assert names == ["0001_first.sql", "0002_second.sql", "0010_later.sql"]


def test_pending_skips_applied_files(tmp_path):
    files = [tmp_path / "0001_a.sql", tmp_path / "0002_b.sql", tmp_path / "0003_c.sql"]

    result = migrate.pending(files, applied={"0001_a.sql", "0003_c.sql"})

    assert [f.name for f in result] == ["0002_b.sql"]


def test_password_from_url_decodes_escapes():
    assert migrate.password_from_url("postgresql://u:p%40ss%2Fword@host:5432/db") == "p@ss/word"


def test_password_from_url_rejects_missing_password():
    with pytest.raises(migrate.SettingsError):
        migrate.password_from_url("postgresql://u@host:5432/db")


def test_load_settings_reads_admin_url_and_role_passwords():
    admin_url, passwords = migrate.load_settings(ENV)

    assert admin_url == ENV["DATABASE_ADMIN_URL"]
    assert passwords == {"ingest": "ingest_pw", "analyst_ro": "analyst_pw"}


@pytest.mark.parametrize("missing", sorted(ENV))
def test_load_settings_names_the_missing_variable(missing):
    env = {key: value for key, value in ENV.items() if key != missing}

    with pytest.raises(migrate.SettingsError, match=missing):
        migrate.load_settings(env)


def test_load_settings_error_does_not_leak_the_url():
    env = ENV | {"INGEST_DATABASE_URL": "postgresql://ingest@secret-host:5433/highbury"}

    with pytest.raises(migrate.SettingsError) as error:
        migrate.load_settings(env)

    assert "secret-host" not in str(error.value)


def test_fresh_database_gets_all_tables(db):
    assert public_tables(db.admin_url) == TABLES | {"schema_migrations"}


def test_second_run_applies_nothing(db, settings):
    _, passwords = settings

    assert migrate.apply(db.admin_url, passwords) == []


def test_main_exits_zero_when_nothing_to_apply(db, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_ADMIN_URL", db.admin_url)

    assert migrate.main() == 0
    assert capsys.readouterr().out.strip() == "Nothing to apply."


def test_failing_migration_leaves_nothing_behind(empty_db, tmp_path, monkeypatch, capsys):
    (tmp_path / "0001_good.sql").write_text("CREATE TABLE kept (id int);")
    (tmp_path / "0002_bad.sql").write_text("CREATE TABLE half_done (id int); SELECT broken;")

    with pytest.raises(psycopg.Error):
        migrate.apply(empty_db, {}, directory=tmp_path)

    assert public_tables(empty_db) == {"kept", "schema_migrations"}
    with psycopg.connect(empty_db) as conn:
        applied = [row[0] for row in conn.execute("SELECT filename FROM schema_migrations")]
    assert applied == ["0001_good.sql"]

    monkeypatch.setenv("DATABASE_ADMIN_URL", empty_db)
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    assert migrate.main() == 1
    assert "Migration failed" in capsys.readouterr().err
