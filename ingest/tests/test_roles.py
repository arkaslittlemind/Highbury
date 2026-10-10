import psycopg
import pytest

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


def test_analyst_can_select_from_a_view(analyst):
    assert analyst.execute("SELECT count(*) FROM v_shots").fetchone() == (0,)


def test_analyst_can_select_from_a_base_table(analyst):
    assert analyst.execute("SELECT count(*) FROM data_catalog").fetchone() == (0,)


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


def test_ingest_cannot_create_a_table(ingest):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        ingest.execute("CREATE TABLE scratch (id int)")


def test_ingest_cannot_touch_the_migration_log(ingest):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        ingest.execute("DELETE FROM schema_migrations")
