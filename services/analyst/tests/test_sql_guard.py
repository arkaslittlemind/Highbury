import pytest

from analyst.sql_guard import MAX_ROWS, SqlRejected, guard

NOT_A_SELECT = "Only a SELECT statement is allowed."
READ_ONLY = "Only a read-only SELECT is allowed."


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("DROP TABLE shots", NOT_A_SELECT),
        ("INSERT INTO teams (name) VALUES ('Arsenal')", NOT_A_SELECT),
        ("UPDATE shots SET xg = 1", NOT_A_SELECT),
        ("DELETE FROM shots", NOT_A_SELECT),
        ("CREATE TABLE scratch (id int)", NOT_A_SELECT),
        ("CREATE TABLE scratch AS SELECT * FROM v_shots", NOT_A_SELECT),
        ("ALTER ROLE analyst_ro SET statement_timeout = 0", NOT_A_SELECT),
        ("ALTER TABLE shots DROP COLUMN xg", NOT_A_SELECT),
        ("TRUNCATE shots", NOT_A_SELECT),
        ("SET statement_timeout = 0", NOT_A_SELECT),
        ("SET default_transaction_read_only = off", NOT_A_SELECT),
        ("RESET ALL", NOT_A_SELECT),
        ("BEGIN", NOT_A_SELECT),
        ("COMMIT", NOT_A_SELECT),
        ("DO $$ BEGIN DELETE FROM shots; END $$", NOT_A_SELECT),
        ("COPY shots TO STDOUT", NOT_A_SELECT),
        ("EXPLAIN ANALYZE SELECT * FROM v_shots", NOT_A_SELECT),
        ("SHOW statement_timeout", NOT_A_SELECT),
        ("CALL something()", NOT_A_SELECT),
        ("LOCK TABLE shots", NOT_A_SELECT),
        ("GRANT ALL ON shots TO analyst_ro", NOT_A_SELECT),
        ("VALUES (1)", NOT_A_SELECT),
        ("TABLE v_shots", NOT_A_SELECT),
        ("(SELECT * FROM v_shots)", NOT_A_SELECT),
        ("SELEC nonsense", NOT_A_SELECT),
        ("SELECT 1; SELECT 2", "Only one statement is allowed."),
        ("SELECT * FROM v_shots; DROP TABLE shots", "Only one statement is allowed."),
        ("", "The SQL is empty."),
        ("   ;  ", "The SQL is empty."),
        ("-- only a comment", "The SQL is empty."),
        ("SELECT * FROM (", "The SQL does not parse as PostgreSQL."),
        ("SELECT 'open", "The SQL does not parse as PostgreSQL."),
    ],
)
def test_a_statement_that_is_not_one_select_is_rejected(sql, reason):
    with pytest.raises(SqlRejected) as error:
        guard(sql)

    assert str(error.value) == reason


@pytest.mark.parametrize(
    "sql",
    [
        "WITH gone AS (DELETE FROM shots RETURNING *) SELECT * FROM gone",
        "WITH new AS (INSERT INTO teams (name) VALUES ('x') RETURNING *) SELECT * FROM new",
        "WITH up AS (UPDATE shots SET xg = 1 RETURNING *) SELECT * FROM up",
        "SELECT * INTO scratch FROM v_shots",
        "SELECT * FROM v_shots FOR UPDATE",
        "SELECT * FROM v_shots FOR SHARE",
    ],
)
def test_a_select_that_writes_or_locks_is_rejected(sql):
    with pytest.raises(SqlRejected) as error:
        guard(sql)

    assert str(error.value) == READ_ONLY


@pytest.mark.parametrize(
    ("sql", "relation"),
    [
        ("SELECT * FROM shots", "shots"),
        ("SELECT * FROM players", "players"),
        ("SELECT * FROM pg_class", "pg_class"),
        ("SELECT * FROM pg_catalog.pg_class", "pg_catalog.pg_class"),
        ("SELECT * FROM information_schema.tables", "information_schema.tables"),
        ("SELECT * FROM public.v_shots", "public.v_shots"),
        ("SELECT * FROM schema_migrations", "schema_migrations"),
        ('SELECT * FROM "V_SHOTS"', "V_SHOTS"),
        ("SELECT * FROM v_shots s JOIN players p ON p.name = s.player", "players"),
        ("SELECT (SELECT count(*) FROM pg_stat_activity) FROM v_shots", "pg_stat_activity"),
        ("SELECT * FROM v_shots WHERE player IN (SELECT name FROM players)", "players"),
        ("SELECT * FROM v_shots UNION SELECT * FROM shots", "shots"),
        # A CTE cannot see a CTE after it, so pg_class is the real table here.
        (
            "WITH a AS (SELECT * FROM pg_class), pg_class AS (SELECT 1) SELECT * FROM a",
            "pg_class",
        ),
        ("WITH a AS (SELECT * FROM a) SELECT * FROM a", "a"),
    ],
)
def test_a_relation_that_is_not_an_agent_view_is_rejected(sql, relation):
    with pytest.raises(SqlRejected, match="is not allowed") as error:
        guard(sql)

    assert f"The relation {relation} " in str(error.value)


@pytest.mark.parametrize(
    "sql",
    [
        # Outside of the subquery, players is the real table.
        "SELECT * FROM (WITH players AS (SELECT 1) SELECT * FROM players) a, players",
        "WITH a AS (WITH b AS (SELECT 1) SELECT * FROM b) SELECT * FROM a",
    ],
)
def test_a_with_below_the_top_is_rejected(sql):
    with pytest.raises(SqlRejected, match="WITH is allowed only at the start"):
        guard(sql)


def test_a_recursive_with_is_rejected():
    sql = "WITH RECURSIVE n AS (SELECT 1 AS i UNION ALL SELECT i + 1 FROM n) SELECT * FROM n"

    with pytest.raises(SqlRejected, match="WITH RECURSIVE is not allowed"):
        guard(sql)


@pytest.mark.parametrize(
    ("sql", "function"),
    [
        ("SELECT pg_sleep(100)", "pg_sleep"),
        ("SELECT PG_SLEEP(100)", "pg_sleep"),
        ("SELECT pg_catalog.pg_sleep(100)", "pg_sleep"),
        ('SELECT "pg_sleep"(100)', "pg_sleep"),
        ("SELECT pg_terminate_backend(1) FROM v_shots", "pg_terminate_backend"),
        ("SELECT * FROM v_shots WHERE pg_cancel_backend(1)", "pg_cancel_backend"),
        ("SELECT pg_read_file('/etc/passwd')", "pg_read_file"),
        ("SELECT * FROM pg_ls_dir('.')", "pg_ls_dir"),
        ("SELECT set_config('statement_timeout', '0', false)", "set_config"),
        ("SELECT lo_creat(-1)", "lo_creat"),
        ("SELECT query_to_xml('SELECT * FROM players', true, false, '')", "query_to_xml"),
        ("SELECT table_to_xml('players', true, false, '')", "table_to_xml"),
        ("SELECT * FROM dblink('dbname=highbury', 'SELECT 1') AS t(a int)", "dblink"),
    ],
)
def test_a_function_that_can_do_harm_is_rejected(sql, function):
    with pytest.raises(SqlRejected) as error:
        guard(sql)

    assert str(error.value) == f"The function {function} is not allowed."


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT player, goals FROM v_player_season WHERE season = '2003-04'",
        "SELECT * FROM V_Shots",
        'SELECT * FROM "v_shots"',
        "SELECT s.player, m.venue FROM v_shots s JOIN v_matches m ON m.match_id = s.match_id",
        "WITH top AS (SELECT player, goals FROM v_player_season) SELECT * FROM top",
        "WITH a AS (SELECT * FROM v_shots), b AS (SELECT * FROM a) SELECT * FROM b",
        "SELECT player FROM v_shots UNION SELECT player FROM v_passes",
        "SELECT player FROM v_shots WHERE xg > (SELECT avg(xg) FROM v_shots)",
        "SELECT * FROM (SELECT player, sum(xg) AS xg FROM v_shots GROUP BY player) t",
        "SELECT player, rank() OVER (PARTITION BY season ORDER BY goals DESC) FROM v_player_season",
        "SELECT player, round(goals * 90.0 / minutes, 2) AS per_90 FROM v_player_season",
        "SELECT count(*) FILTER (WHERE is_goal) FROM v_shots WHERE player ILIKE '%enry'",
        "SELECT DISTINCT ON (player) player, xg FROM v_shots ORDER BY player, xg DESC",
        "SELECT extract(month FROM match_date), to_char(match_date, 'YYYY') FROM v_matches",
        "SELECT g FROM generate_series(0, 90, 15) g",
        "SELECT 1",
    ],
)
def test_a_read_only_select_on_the_views_is_accepted(sql):
    assert guard(sql).sql


def limited(sql: str) -> tuple[str, bool]:
    result = guard(sql)
    return result.sql, result.capped


def test_a_limit_is_added_when_there_is_none():
    assert limited("SELECT player FROM v_shots") == (
        f"SELECT player FROM v_shots LIMIT {MAX_ROWS}",
        True,
    )


def test_a_smaller_limit_stays():
    assert limited("SELECT player FROM v_shots LIMIT 5") == (
        "SELECT player FROM v_shots LIMIT 5",
        False,
    )


def test_a_limit_at_the_cap_stays():
    assert limited(f"SELECT 1 LIMIT {MAX_ROWS}") == (f"SELECT 1 LIMIT {MAX_ROWS}", False)


@pytest.mark.parametrize("tail", [f"LIMIT {MAX_ROWS + 1}", "LIMIT 100000"])
def test_a_larger_limit_is_lowered(tail):
    assert limited(f"SELECT player FROM v_shots {tail}") == (
        f"SELECT player FROM v_shots LIMIT {MAX_ROWS}",
        True,
    )


@pytest.mark.parametrize(
    "tail",
    [
        "LIMIT ALL",
        "LIMIT NULL",
        "LIMIT (5)",
        "LIMIT 2 + 3",
        "LIMIT 5 + 100000",
        "LIMIT (SELECT 100000)",
        "LIMIT CAST(5 AS INT)",
        "FETCH FIRST 100000 ROWS ONLY",
        "FETCH FIRST ROWS ONLY",
        "FETCH FIRST 3 ROWS WITH TIES",
    ],
)
def test_a_limit_that_is_not_a_plain_small_number_stays_inside_the_cap(tail):
    # The statement can mean fewer rows than the cap, so it is not rewritten.
    assert limited(f"SELECT player FROM v_shots ORDER BY player {tail}") == (
        f"SELECT * FROM (SELECT player FROM v_shots ORDER BY player {tail}) AS q LIMIT {MAX_ROWS}",
        True,
    )


def test_fetch_first_row_only_stays_inside_the_cap():
    sql, capped = limited("SELECT player FROM v_shots FETCH FIRST ROW ONLY")

    assert sql.startswith("SELECT * FROM (SELECT player FROM v_shots FETCH FIRST ")
    assert sql.endswith(f") AS q LIMIT {MAX_ROWS}")
    assert capped


def test_a_cte_statement_with_a_computed_limit_is_capped_as_a_whole():
    sql = "WITH a AS (SELECT player FROM v_shots) SELECT * FROM a UNION SELECT '' LIMIT 2 + 3"

    assert limited(sql) == (f"SELECT * FROM ({sql}) AS q LIMIT {MAX_ROWS}", True)


def test_a_small_fetch_first_stays():
    sql, capped = limited("SELECT player FROM v_shots FETCH FIRST 5 ROWS ONLY")

    assert sql == "SELECT player FROM v_shots FETCH FIRST 5 ROWS ONLY"
    assert not capped


def test_an_offset_stays_next_to_the_added_limit():
    assert limited("SELECT player FROM v_shots OFFSET 10") == (
        f"SELECT player FROM v_shots LIMIT {MAX_ROWS} OFFSET 10",
        True,
    )


def test_the_limit_goes_on_the_whole_union():
    assert limited("SELECT player FROM v_shots UNION ALL SELECT player FROM v_passes") == (
        f"SELECT player FROM v_shots UNION ALL SELECT player FROM v_passes LIMIT {MAX_ROWS}",
        True,
    )


def test_the_limit_goes_on_the_outer_query_of_a_cte():
    sql = "WITH a AS (SELECT player FROM v_shots LIMIT 100000) SELECT * FROM a"

    assert limited(sql) == (
        f"WITH a AS (SELECT player FROM v_shots LIMIT 100000) SELECT * FROM a LIMIT {MAX_ROWS}",
        True,
    )


def test_a_limit_in_a_subquery_does_not_count_as_the_outer_limit():
    sql = "SELECT * FROM (SELECT player FROM v_shots LIMIT 3) t"

    assert limited(sql) == (
        f"SELECT * FROM (SELECT player FROM v_shots LIMIT 3) AS t LIMIT {MAX_ROWS}",
        True,
    )


def test_the_statement_to_run_is_written_from_the_parsed_tree():
    # A comment cannot hide a second meaning from the database.
    assert guard("SELECT 1 /* ; DROP TABLE shots */ -- x").sql.startswith("SELECT 1 ")


def test_sql_that_is_nested_too_deeply_is_rejected():
    with pytest.raises(SqlRejected, match="nested too deeply"):
        guard("SELECT " + "(" * 5000 + "1" + ")" * 5000)


def test_a_function_that_runs_a_sql_string_is_rejected():
    with pytest.raises(SqlRejected, match="The function ts_stat is not allowed"):
        guard("SELECT * FROM ts_stat('SELECT to_tsvector(name) FROM players')")


def test_a_rejected_statement_is_not_logged(caplog):
    with pytest.raises(SqlRejected):
        guard("RESET ALL")

    assert caplog.text == ""


def test_a_nul_character_cannot_cut_the_limit_off():
    # The client library ends the text at a NUL, so the limit after it would be lost.
    with pytest.raises(SqlRejected, match="NUL character"):
        guard("SELECT g FROM generate_series(1, 600) AS g\x00x")


def test_a_character_that_cannot_be_sent_is_rejected():
    with pytest.raises(SqlRejected, match="cannot read"):
        guard("SELECT '\ud800'")


def test_a_name_folds_as_in_postgresql_and_not_as_in_python():
    # Python lowers the Kelvin sign to "k". PostgreSQL does not, so there the CTE
    # has a different name and pg_locks is the real system view.
    with pytest.raises(SqlRejected, match="The relation pg_locks is not allowed"):
        guard("WITH pg_loc\u212as AS (SELECT 1) SELECT locktype FROM pg_locks")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1" + "::int" * 3000,
        "SELECT * FROM " + "(SELECT * FROM " * 400 + "v_shots" + ") t" * 400,
    ],
)
def test_sql_that_is_too_deep_to_write_back_is_rejected(sql):
    with pytest.raises(SqlRejected, match="nested too deeply"):
        guard(sql)
