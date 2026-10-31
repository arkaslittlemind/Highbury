import psycopg
import pytest

from ingest import migrate

WRITE_DENIED = (psycopg.errors.InsufficientPrivilege, psycopg.errors.ReadOnlySqlTransaction)


@pytest.fixture
def analyst(db):
    with psycopg.connect(db.analyst_url, autocommit=True) as conn:
        yield conn


@pytest.fixture
def ingest(db):
    with psycopg.connect(db.ingest_url) as conn:
        yield conn
        conn.rollback()


@pytest.mark.parametrize(
    "view",
    [
        "v_shots",
        "v_passes",
        "v_substitutions",
        "v_league_matches",
        "v_league_table",
        "v_fpl_player_match",
        "v_player_match_advanced",
        "v_touches",
    ],
)
def test_analyst_can_select_from_a_view(analyst, view):
    assert analyst.execute(f"SELECT count(*) FROM {view}").fetchone() == (0,)


@pytest.mark.parametrize("table", ["data_catalog", "team_match_stats", "fpl_player_match"])
def test_analyst_can_select_from_a_base_table(analyst, table):
    assert analyst.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)


def test_analyst_cannot_insert(analyst):
    with pytest.raises(WRITE_DENIED):
        analyst.execute("INSERT INTO teams (name) VALUES ('Arsenal')")


def test_analyst_cannot_insert_after_leaving_read_only_mode(analyst):
    analyst.execute("SET default_transaction_read_only = off")

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        analyst.execute("INSERT INTO teams (name) VALUES ('Arsenal')")


def test_analyst_cannot_create_a_table(analyst):
    analyst.execute("SET default_transaction_read_only = off")

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        analyst.execute("CREATE TABLE scratch (id int)")


def test_analyst_cannot_create_a_temporary_table(analyst):
    analyst.execute("SET default_transaction_read_only = off")

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        analyst.execute("CREATE TEMP TABLE scratch (id int)")


def test_analyst_cannot_read_the_migration_log(analyst):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        analyst.execute("SELECT * FROM schema_migrations")


def test_analyst_statement_times_out_after_five_seconds(analyst):
    assert analyst.execute("SHOW statement_timeout").fetchone() == ("5s",)

    with pytest.raises(psycopg.errors.QueryCanceled):
        analyst.execute("SELECT pg_sleep(6)")


def test_ingest_can_insert(ingest):
    ingest.execute("INSERT INTO teams (name) VALUES ('Arsenal')")

    assert ingest.execute("SELECT name FROM teams").fetchall() == [("Arsenal",)]


def test_ingest_can_write_team_match_stats(ingest):
    ingest.execute("DELETE FROM team_match_stats")

    assert ingest.execute("SELECT count(*) FROM team_match_stats").fetchone() == (0,)


def test_ingest_cannot_create_a_table(ingest):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        ingest.execute("CREATE TABLE scratch (id int)")


def test_ingest_cannot_touch_the_migration_log(ingest):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        ingest.execute("DELETE FROM schema_migrations")


def test_ingest_can_use_the_id_sequences(ingest):
    value = ingest.execute("SELECT nextval(pg_get_serial_sequence('teams', 'id'))").fetchone()[0]

    assert value >= 1


def analyst_defaults(url: str) -> tuple[str, str]:
    with psycopg.connect(url, autocommit=True) as conn:
        timeout = conn.execute("SHOW statement_timeout").fetchone()[0]
        read_only = conn.execute("SHOW default_transaction_read_only").fetchone()[0]
    return timeout, read_only


ROLE_WIDE = "ALTER ROLE analyst_ro SET {} = {}"
ONE_DATABASE = "ALTER ROLE analyst_ro IN DATABASE {database} SET {} = {}"


@pytest.mark.parametrize("statement", [ROLE_WIDE, ONE_DATABASE], ids=["role-wide", "one-database"])
def test_runner_restores_analyst_defaults_the_role_removed(db, settings, statement):
    _, passwords = settings
    try:
        with psycopg.connect(db.analyst_url, autocommit=True) as conn:
            database = conn.execute("SELECT current_database()").fetchone()[0]
            conn.execute("SET default_transaction_read_only = off")
            conn.execute(statement.format("statement_timeout", "0", database=database))
            conn.execute(
                statement.format("default_transaction_read_only", "off", database=database)
            )
        assert analyst_defaults(db.analyst_url) == ("0", "off")

        migrate.apply(db.admin_url, passwords)

        assert analyst_defaults(db.analyst_url) == ("5s", "on")
    finally:
        # The role is shared with the developer database, so never leave it open.
        migrate.apply(db.admin_url, passwords)
