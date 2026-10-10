import pytest

from analyst import db as read_path

TIMEOUT_MS = 2000
INSERT = "INSERT INTO teams (name) VALUES ('Arsenal')"


def team_count(conn) -> int:
    return conn.execute("SELECT count(*) FROM teams").fetchone()[0]


def test_a_select_returns_columns_and_rows(analyst_env):
    result = read_path.read("SELECT 1 AS one, 'a' AS letter UNION ALL SELECT 2, 'b'", TIMEOUT_MS)

    assert result.columns == ["one", "letter"]
    assert result.rows == [(1, "a"), (2, "b")]


def test_a_parameter_goes_to_the_server_apart_from_the_sql(analyst_env):
    name = "Henry'; DROP TABLE teams; --"

    result = read_path.read("SELECT %s::text AS name", TIMEOUT_MS, [name])

    assert result.rows == [(name,)]


def test_a_percent_sign_in_the_sql_stays_literal(analyst_env):
    result = read_path.read("SELECT 'Thierry Henry' LIKE '%enry' AS found", TIMEOUT_MS)

    assert result.rows == [(True,)]


def test_the_transaction_is_read_only_and_has_the_timeout_of_the_call(analyst_env):
    result = read_path.read(
        "SELECT current_setting('transaction_read_only'), current_setting('statement_timeout')",
        1234,
    )

    assert result.rows == [("on", "1234ms")]


@pytest.mark.parametrize(
    "statement",
    [INSERT, "CREATE TABLE scratch (id int)", "CREATE TEMP TABLE scratch (id int)"],
)
def test_a_write_fails_with_no_guard_in_front(analyst_env, ingest, statement):
    with pytest.raises(read_path.QueryFailed):
        read_path.read(statement, TIMEOUT_MS)

    assert team_count(ingest) == 0


def test_a_write_fails_for_a_role_that_can_write(analyst_env, analyst_url, ingest):
    # The wrong URL in the settings must not turn the read path into a write path.
    analyst_url(analyst_env.ingest_url)

    with pytest.raises(read_path.QueryFailed, match="read-only transaction"):
        read_path.read(INSERT, TIMEOUT_MS)

    assert team_count(ingest) == 0


def test_a_statement_cannot_leave_read_only_mode_for_the_next_call(
    analyst_env, analyst_url, ingest
):
    # As the ingest role, so that only the read-only transaction stops the write.
    analyst_url(analyst_env.ingest_url)
    read_path.read("SELECT set_config('default_transaction_read_only', 'off', false)", TIMEOUT_MS)

    with pytest.raises(read_path.QueryFailed, match="read-only transaction"):
        read_path.read(INSERT, TIMEOUT_MS)

    assert team_count(ingest) == 0


def test_a_slow_statement_is_stopped_at_the_timeout(analyst_env):
    with pytest.raises(read_path.QueryTimeout):
        read_path.read("SELECT pg_sleep(1)", 200)


def test_a_statement_cannot_keep_a_longer_timeout_for_the_next_call(analyst_env):
    read_path.read("SELECT set_config('statement_timeout', '0', false)", TIMEOUT_MS)

    with pytest.raises(read_path.QueryTimeout):
        read_path.read("SELECT pg_sleep(1)", 200)


@pytest.mark.parametrize(
    "statements",
    [
        "SELECT 1; SELECT 2",
        f"SELECT 1; {INSERT}",
        "SET statement_timeout = 0; SELECT pg_sleep(1)",
        "COMMIT; SELECT 1",
    ],
)
def test_a_string_with_two_statements_fails(analyst_env, statements):
    with pytest.raises(read_path.QueryFailed, match="multiple commands"):
        read_path.read(statements, 200)


def test_a_nul_character_fails_before_the_server_gets_a_cut_statement(analyst_env):
    with pytest.raises(read_path.QueryFailed, match="NUL character"):
        read_path.read("SELECT 1\x00, 2", TIMEOUT_MS)


def test_a_character_that_cannot_be_sent_fails_as_a_query(analyst_env):
    with pytest.raises(read_path.QueryFailed, match="cannot read"):
        read_path.read("SELECT '\ud800'", TIMEOUT_MS)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("SELECT nope", 'column "nope" does not exist'),
        # The server reports these two in an error class of connection problems.
        ("SELECT $1", "bind message supplies 0 parameters"),
        ("SELECT 1 / 0", "division by zero"),
    ],
)
def test_an_error_of_the_server_keeps_its_message(analyst_env, sql, message):
    with pytest.raises(read_path.QueryFailed, match=message):
        read_path.read(sql, TIMEOUT_MS)


def test_a_whole_row_and_json_come_back_as_readable_values(analyst_env):
    result = read_path.read(
        """SELECT t, '{"a": 1}'::jsonb FROM (SELECT 1 AS x, 'y' AS z) t""", 2000
    )

    # psycopg reads a row with no named type as a tuple of text values.
    assert result.rows == [(("1", "y"), {"a": 1})]


def test_an_unreachable_database_is_reported_without_the_url(analyst_url, monkeypatch):
    # Nothing listens on port 1. One address and a short limit keep the test short.
    monkeypatch.setattr(read_path, "CONNECT_TIMEOUT_SECONDS", 2)
    analyst_url("postgresql://analyst_ro:hunter2@127.0.0.1:1/none")

    with pytest.raises(read_path.DatabaseUnavailable) as error:
        read_path.read("SELECT 1", TIMEOUT_MS)

    assert str(error.value) == "The database is not reachable."


def test_a_url_that_does_not_parse_is_reported_without_the_password(analyst_url):
    # psycopg repeats a URL it cannot parse in its own error text.
    analyst_url("postgresql//analyst_ro:hunter2@localhost/none")

    with pytest.raises(read_path.DatabaseUnavailable) as error:
        read_path.read("SELECT 1", TIMEOUT_MS)

    assert "hunter2" not in str(error.value)
