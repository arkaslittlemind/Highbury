import os
import re
from datetime import date
from urllib.parse import urlsplit, urlunsplit

import pytest

from analyst import db as read_path
from analyst import tools
from analyst.sql_guard import AGENT_VIEWS, MAX_ROWS
from ingest import curated, load


def shot(source_id, player, outcome, xg):
    return load.ShotRow(
        source_id, "m1", player, "Arsenal", 12, 104.0, 36.0, xg, outcome, "right foot", "open play"
    )


def season(season_id, label, source, players, shots=()) -> load.SeasonRows:
    """One Arsenal home match. Each player is (source id, name, source name, team)."""
    return load.SeasonRows(
        season_id=season_id,
        season_label=label,
        data_level="SHOT",
        source=source,
        teams=["Arsenal", "Everton"],
        players=[load.PlayerRow(pid, name, alias, None) for pid, name, alias, _ in players],
        matches=[load.MatchRow("m1", date(season_id, 8, 16), "Arsenal", "Everton", 2, 1, None)],
        shots=list(shots),
        events=[],
        stats=[load.StatRow(pid, "m1", team, 90, 0, 0, None, None) for pid, _, _, team in players],
    )


@pytest.fixture
def seeded(analyst_env, ingest):
    """Two small seasons with aliases and the catalog, as the analyst can read them."""
    load.load(
        ingest,
        season(
            2003,
            "2003-04",
            "statsbomb",
            [
                ("10", "Thierry Henry", "Thierry Henry", "Arsenal"),
                ("11", "Robert Pirès", "Robert Pirès", "Arsenal"),
                ("12", "Ashley Cole", "Ashley Cole", "Arsenal"),
                ("13", "Joe Cole", "Joseph John Cole", "Everton"),
            ],
            [shot("s1", "10", "goal", 0.25), shot("s2", "10", "saved", 0.5)],
        ),
    )
    load.load(
        ingest,
        season(
            2025,
            "2025-26",
            "understat",
            [
                ("7", "Bukayo Saka", "Bukayo Saka", "Arsenal"),
                ("9", "Micky van de Ven", "Micky van de Ven", "Everton"),
            ],
        ),
    )
    curated.load_aliases(
        ingest,
        [
            curated.AliasEntry("2003-04", "Thierry Henry", ("Henry", "Titi")),
            curated.AliasEntry("2003-04", "Robert Pirès", ("Pires",)),
            curated.AliasEntry("2025-26", "Bukayo Saka", ("Saka", "B. Saka")),
        ],
    )
    curated.load_catalog(ingest)
    # The tools open their own connections, so they must see these rows.
    ingest.commit()


@pytest.fixture
def no_database(analyst_url):
    """A URL that the server refuses at once, so the test does not wait for a timeout."""
    url = urlsplit(os.environ["ANALYST_DATABASE_URL"])._replace(path="/highbury_no_such_database")
    analyst_url(urlunsplit(url))


def test_run_sql_returns_the_rows_and_the_statement_that_ran(seeded):
    result = tools.run_sql(
        "SELECT player, count(*) AS shots, sum(xg) AS xg FROM v_shots GROUP BY player"
    )

    assert result.ok and result.error is None
    assert result.sql == (
        f"SELECT player, COUNT(*) AS shots, SUM(xg) AS xg FROM v_shots GROUP BY player"
        f" LIMIT {MAX_ROWS}"
    )
    assert result.columns == ["player", "shots", "xg"]
    assert result.rows == [["Thierry Henry", 2, 0.75]]
    assert result.row_count == 1
    assert not result.limit_reached


def test_each_call_has_its_own_call_id(seeded):
    first, second, failed = tools.run_sql("SELECT 1"), tools.run_sql("SELECT 1"), tools.run_sql("")

    ids = {first.call_id, second.call_id, failed.call_id}
    assert len(ids) == 3
    assert all(re.fullmatch(r"q_[0-9a-f]{8}", call_id) for call_id in ids)


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("DROP TABLE shots", "Only a SELECT statement is allowed."),
        ("SELECT * FROM shots", "The relation shots is not allowed."),
        ("SELECT pg_sleep(60)", "The function pg_sleep is not allowed."),
        ("SELECT 1\x00", "The SQL has a NUL character."),
        ("SELECT '\ud800'", "The SQL has a character that the database cannot read."),
        ("SELECT 1" + "::int" * 3000, "The SQL is nested too deeply."),
    ],
)
def test_a_rejected_statement_returns_the_reason_and_reaches_no_database(no_database, sql, reason):
    result = tools.run_sql(sql)

    assert not result.ok
    assert result.error.startswith(reason)
    assert result.sql is None
    assert result.rows == []


def test_a_database_error_comes_back_as_text(seeded):
    result = tools.run_sql("SELECT nope FROM v_shots")

    assert not result.ok
    assert result.error == 'column "nope" does not exist'
    assert result.sql == f"SELECT nope FROM v_shots LIMIT {MAX_ROWS}"


def test_a_refused_connection_comes_back_as_text_without_the_url(no_database):
    result = tools.run_sql("SELECT 1")

    assert not result.ok
    assert result.error == "The database is not reachable."


def test_a_missing_url_comes_back_as_text(analyst_url):
    analyst_url(None)

    assert tools.run_sql("SELECT 1").error == "ANALYST_DATABASE_URL is not set"


def test_run_sql_gives_the_five_second_timeout_to_the_read_path(monkeypatch):
    calls = []

    def read(sql, timeout_ms, params=None):
        calls.append((sql, timeout_ms, params))
        return read_path.Rows(["n"], [(1,)])

    monkeypatch.setattr(tools.db, "read", read)

    assert tools.run_sql("SELECT 1 AS n").rows == [[1]]
    assert calls == [(f"SELECT 1 AS n LIMIT {MAX_ROWS}", 5000, None)]


def test_a_statement_that_runs_too_long_comes_back_as_text(seeded, monkeypatch):
    # A short timeout proves the path with no long wait.
    monkeypatch.setattr(tools, "STATEMENT_TIMEOUT_MS", 200)

    result = tools.run_sql("SELECT count(*) FROM generate_series(1, 2000000000)")

    assert not result.ok
    assert result.error == "The query took longer than 5 seconds and was stopped."


def test_the_limit_of_the_guard_cuts_the_rows_and_says_so(seeded):
    result = tools.run_sql(f"SELECT g FROM generate_series(1, {MAX_ROWS + 100}) g")

    assert result.row_count == MAX_ROWS == len(result.rows)
    assert result.limit_reached


def test_the_limit_of_the_statement_does_not_count_as_cut(seeded):
    result = tools.run_sql(f"SELECT g FROM generate_series(1, 9999) g LIMIT {MAX_ROWS}")

    assert result.row_count == MAX_ROWS
    assert not result.limit_reached


@pytest.mark.parametrize(
    ("tail", "rows"),
    [
        ("FETCH FIRST ROW ONLY", 1),
        ("LIMIT (5)", 5),
        ("LIMIT 2 + 3", 5),
        ("LIMIT 100000", MAX_ROWS),
        ("LIMIT ALL", MAX_ROWS),
        ("FETCH FIRST 100000 ROWS ONLY", MAX_ROWS),
    ],
)
def test_a_limit_in_any_form_gives_its_rows_but_never_more_than_the_cap(seeded, tail, rows):
    result = tools.run_sql(f"SELECT g FROM generate_series(1, 9999) g ORDER BY g {tail}")

    assert result.error is None
    assert result.row_count == rows
    assert result.rows[0] == [1]


def test_values_come_back_in_a_form_that_json_can_hold(seeded):
    result = tools.run_sql(
        "SELECT round(0.756, 2) AS rate, sum(match_id * 0 + 3) AS whole, match_date,"
        " venue, home_goals > away_goals AS won, xg.total FROM v_matches,"
        " (SELECT sum(xg) AS total FROM v_shots) AS xg WHERE season = '2003-04'"
        " GROUP BY match_date, venue, home_goals, away_goals, xg.total"
    )

    assert result.error is None
    assert result.rows == [[0.76, 3, "2003-08-16", None, True, 0.75]]
    assert [type(value) for value in result.rows[0]] == [float, int, str, type(None), bool, float]
    assert result.model_dump_json()


def test_a_whole_row_comes_back_as_text(seeded):
    result = tools.run_sql("SELECT m FROM v_matches m WHERE season = '2003-04'")

    assert result.error is None
    assert result.rows[0][0].endswith(",2003-04,2003-08-16,Arsenal,Everton,2,1,)")


def test_the_catalog_has_every_row_of_both_seasons(seeded):
    result = tools.get_data_catalog()

    assert result.error is None
    assert len(result.rows) == 14
    assert [(row.season, row.metric) for row in result.rows] == sorted(
        (row.season, row.metric) for row in result.rows
    )


@pytest.mark.parametrize("label", ["2025-26", " 2025-26 ", "2025/26", "2025\N{EN DASH}26"])
def test_the_catalog_of_one_season_says_what_is_not_there(seeded, label):
    result = tools.get_data_catalog(label)

    assert len(result.rows) == 7
    assert {row.season for row in result.rows} == {"2025-26"}
    passes = next(row for row in result.rows if row.metric == "passes")
    assert not passes.available
    assert passes.source is None
    assert "shot map" in passes.notes


def test_an_unknown_season_lists_the_known_seasons(seeded):
    result = tools.get_data_catalog("1997-98")

    assert result.rows == []
    assert result.error == "Unknown season '1997-98'. Known seasons: 2003-04, 2025-26."


def test_the_schema_describes_the_five_views_and_every_column(seeded, analyst):
    result = tools.get_schema()

    assert result.error is None
    assert [view.name for view in result.views] == list(AGENT_VIEWS)
    for view in result.views:
        cursor = analyst.execute(f"SELECT * FROM {view.name} LIMIT 0")
        assert [column.name for column in view.columns] == [c.name for c in cursor.description]
        assert view.description
        assert all(column.description and column.type for column in view.columns)
    shots = result.views[1]
    assert shots.description == "One row per shot, both seasons."
    assert {column.name: column.type for column in shots.columns}["is_goal"] == "boolean"


@pytest.mark.parametrize("tool", [tools.get_data_catalog, tools.get_schema])
def test_a_tool_reports_a_database_it_cannot_reach_as_text(no_database, tool):
    assert tool().error == "The database is not reachable."


@pytest.mark.parametrize(
    ("name", "player", "matched_on"),
    [
        ("Titi", "Thierry Henry", "Titi"),
        ("henry", "Thierry Henry", "Henry"),
        ("  THIERRY   HENRY ", "Thierry Henry", "Thierry Henry"),
        ("Pires", "Robert Pirès", "Pires"),
        ("robert pirès", "Robert Pirès", "Robert Pirès"),
    ],
)
def test_an_exact_name_or_alias_finds_the_player(seeded, name, player, matched_on):
    result = tools.resolve_player(name)

    assert result.status == "found"
    (match,) = result.matches
    assert (match.player, match.matched_on) == (player, matched_on)
    assert (match.method, match.score) == ("exact", 100.0)
    assert (match.seasons, match.teams) == (["2003-04"], ["Arsenal"])


def test_an_exact_alias_stops_the_search_for_close_names(seeded):
    result = tools.resolve_player("B. Saka")

    assert [(m.player, m.method, m.seasons) for m in result.matches] == [
        ("Bukayo Saka", "exact", ["2025-26"])
    ]


def test_a_nickname_with_a_surname_finds_the_player_by_closeness(seeded):
    result = tools.resolve_player("Titi Henry")

    assert result.status == "found"
    assert result.matches[0].player == "Thierry Henry"
    assert result.matches[0].method == "fuzzy"
    assert result.matches[0].score >= tools.FUZZY_CUTOFF


def test_a_misspelled_name_finds_the_player_by_closeness(seeded):
    result = tools.resolve_player("Bukayo Sakka")

    assert result.status == "found"
    assert result.matches[0].player == "Bukayo Saka"


def test_a_name_that_is_close_to_two_players_is_ambiguous(seeded):
    result = tools.resolve_player("Cole")

    assert result.status == "ambiguous"
    assert [match.player for match in result.matches] == ["Ashley Cole", "Joe Cole"]
    assert result.matches[0].score >= result.matches[1].score
    assert [match.teams for match in result.matches] == [["Arsenal"], ["Everton"]]


def test_a_shared_short_word_is_not_a_match(seeded):
    assert tools.resolve_player("Van Persie").status == "not_found"


def test_a_name_that_is_close_to_nobody_is_not_found(seeded):
    result = tools.resolve_player("Zinedine Zidane")

    assert (result.status, result.matches, result.error) == ("not_found", [], None)


@pytest.mark.parametrize("name", ["", "   "])
def test_an_empty_name_is_not_found_with_a_reason(seeded, name):
    result = tools.resolve_player(name)

    assert (result.status, result.error) == ("not_found", "The player name is empty.")


def test_a_name_is_data_and_never_sql(seeded):
    result = tools.resolve_player("x'; DROP TABLE players; --")

    assert result.status == "not_found"
    assert tools.resolve_player("Titi").status == "found"


def test_a_lookup_that_did_not_run_is_an_error_and_not_a_missing_player(no_database):
    result = tools.resolve_player("Henry")

    assert (result.status, result.error) == ("error", "The database is not reachable.")


def names(*rows):
    return [(player_id, player, text) for player_id, player, text in rows]


def test_the_ranking_puts_the_closest_player_first_with_no_database():
    method, ranked = tools.rank_players(
        "Thiery Henri",
        names((1, "Thierry Henry", "Thierry Henry"), (1, "Thierry Henry", "Titi"), (2, "Bo", "Bo")),
    )

    assert method == "fuzzy"
    assert [(c.player_id, c.matched_on) for c in ranked] == [(1, "Thierry Henry")]


def test_two_players_of_one_name_are_two_candidates():
    method, ranked = tools.rank_players(
        "gabriel", names((5, "Gabriel", "Gabriel"), (9, "Gabriel", "Gabriel"))
    )

    assert method == "exact"
    assert [c.player_id for c in ranked] == [5, 9]


def test_the_ranking_keeps_five_players_at_most():
    rows = names(*[(i, f"Cole {i}", "Cole") for i in range(8)])

    assert len(tools.rank_players("Cole", rows)[1]) == tools.MAX_MATCHES
