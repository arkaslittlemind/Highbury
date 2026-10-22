import re

import pytest

from analyst import db as read_path
from analyst import tools
from analyst.sql_guard import AGENT_VIEWS, MAX_ROWS
from ingest.curated import CATALOG


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
    assert len(result.rows) == len(CATALOG)
    assert [(row.season, row.metric) for row in result.rows] == sorted(
        (row.season, row.metric) for row in result.rows
    )


@pytest.mark.parametrize("label", ["2025-26", " 2025-26 ", "2025/26", "2025\N{EN DASH}26"])
def test_the_catalog_of_one_season_says_what_is_not_there(seeded, label):
    result = tools.get_data_catalog(label)

    assert len(result.rows) == sum(row[0] == "2025-26" for row in CATALOG)
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


def test_build_chart_gives_a_shot_map_with_the_rows_of_the_statement(seeded):
    result = tools.build_chart(
        "shot_map", "SELECT * FROM v_shots WHERE player = 'Thierry Henry' ORDER BY xg", " Henry "
    )

    assert result.ok and result.error is None
    assert result.sql == (
        f"SELECT * FROM v_shots WHERE player = 'Thierry Henry' ORDER BY xg LIMIT {MAX_ROWS}"
    )
    assert result.row_count == 2
    assert re.fullmatch(r"q_[0-9a-f]{8}", result.call_id)
    assert re.fullmatch(r"c_[0-9a-f]{8}", result.chart.id)
    assert (result.chart.type, result.chart.title) == ("shot_map", "Henry")
    assert [shot.model_dump() for shot in result.chart.shots] == [
        {
            "x": 104.0,
            "y": 36.0,
            "xg": xg,
            "outcome": outcome,
            "minute": 12,
            "opponent": "Everton",
            "player": "Thierry Henry",
            "season": "2003-04",
            "match_date": "2003-08-16",
        }
        for xg, outcome in [(0.25, "goal"), (0.5, "saved")]
    ]
    assert result.model_dump_json()


COMPARE = (
    "SELECT player, season, {metrics} FROM v_player_season"
    " WHERE player IN ('Thierry Henry', 'Bukayo Saka') ORDER BY season"
)


def test_build_chart_compares_two_players_on_the_metrics_of_the_statement(seeded):
    result = tools.build_chart("compare_bars", COMPARE.format(metrics="minutes, shots"), "Eras")

    assert result.error is None
    assert result.chart.model_dump() == {
        "type": "compare_bars",
        "id": result.chart.id,
        "title": "Eras",
        "series": [
            {"player": "Thierry Henry", "season": "2003-04"},
            {"player": "Bukayo Saka", "season": "2025-26"},
        ],
        "metrics": [
            {"name": "minutes", "values": [90.0, 90.0]},
            {"name": "shots", "values": [2.0, 0.0]},
        ],
    }


def test_build_chart_refuses_a_metric_that_one_player_does_not_have(seeded):
    result = tools.build_chart("compare_bars", COMPARE.format(metrics="minutes, xa"), "Eras")

    assert result.chart is None
    assert result.error == (
        "The metric xa is null for Thierry Henry."
        " A comparison uses only metrics that both players have."
    )


HUGE = "power(10::numeric, 400)"


@pytest.mark.parametrize(
    ("chart_type", "sql", "reason"),
    [
        (
            "compare_bars",
            COMPARE.format(metrics=f"{HUGE} AS goals"),
            "The metric goals is not a number that a chart can hold for Thierry Henry.",
        ),
        (
            "pass_network",
            f"SELECT player, recipient, {HUGE} AS passes, avg(x) AS x, avg(y) AS y FROM v_passes"
            " WHERE outcome IS NULL GROUP BY player, recipient",
            "The pass counts of",
        ),
    ],
)
def test_build_chart_gives_text_for_a_number_that_is_too_large(seeded, chart_type, sql, reason):
    result = tools.build_chart(chart_type, sql, "Too large")

    assert (result.ok, result.chart) == (False, None)
    assert result.error.startswith(reason)


def test_build_chart_gives_a_pass_network_from_the_grouped_passes(seeded):
    result = tools.build_chart(
        "pass_network",
        "SELECT player, recipient, count(*) AS passes, avg(x) AS x, avg(y) AS y FROM v_passes"
        " WHERE team = 'Arsenal' AND outcome IS NULL GROUP BY player, recipient ORDER BY player",
        "Arsenal passes",
    )

    assert result.error is None
    assert [node.model_dump() for node in result.chart.nodes] == [
        {"player": "Robert Pirès", "x": 50.0, "y": 30.0, "passes": 1},
        {"player": "Thierry Henry", "x": 70.0, "y": 30.0, "passes": 2},
    ]
    assert [edge.model_dump() for edge in result.chart.edges] == [
        {"source": "Robert Pirès", "target": "Thierry Henry", "passes": 1},
        {"source": "Thierry Henry", "target": "Robert Pirès", "passes": 2},
    ]


def test_build_chart_gives_an_xg_timeline_of_the_shots_of_one_match(seeded):
    result = tools.build_chart(
        "xg_timeline",
        # Both shots are in minute 12, so xg fixes their order.
        "SELECT match_id, team, opponent, minute, xg, is_goal, player FROM v_shots"
        " ORDER BY minute, xg",
        "Arsenal v Everton",
    )

    assert result.error is None
    assert result.chart.model_dump()["teams"] == [
        {
            "team": "Arsenal",
            "xg": 0.75,
            "shots": [
                {
                    "minute": 12,
                    "xg": 0.25,
                    "total": 0.25,
                    "is_goal": True,
                    "player": "Thierry Henry",
                },
                {
                    "minute": 12,
                    "xg": 0.5,
                    "total": 0.75,
                    "is_goal": False,
                    "player": "Thierry Henry",
                },
            ],
        },
        # Everton has no shot in the seeded match.
        {"team": "Everton", "xg": 0.0, "shots": []},
    ]


@pytest.mark.parametrize(
    ("chart_type", "title", "reason"),
    [
        ("pie", "Henry", "Unknown chart type 'pie'. Known types: shot_map, compare_bars,"),
        ("shot_map", "  ", "The title must have 1 to 120 characters."),
    ],
)
def test_build_chart_refuses_a_bad_request_and_runs_no_query(
    no_database, chart_type, title, reason
):
    result = tools.build_chart(chart_type, "SELECT * FROM v_shots", title)

    assert not result.ok
    assert result.error.startswith(reason)
    assert (result.chart, result.call_id, result.sql) == (None, None, None)


SHOT = "104.0 AS x, 36.0 AS y, 0.25 AS xg, 'goal' AS outcome, 12 AS minute, 'Everton' AS opponent"


@pytest.mark.parametrize(
    ("sql", "ran", "rows", "reason"),
    [
        ("DROP TABLE shots", False, 0, "Only a SELECT statement is allowed."),
        ("SELECT nope FROM v_shots", True, 0, 'column "nope" does not exist'),
        (
            f"SELECT {SHOT} FROM generate_series(1, {MAX_ROWS + 1})",
            True,
            MAX_ROWS,
            f"The query reached the limit of {MAX_ROWS} rows. A chart needs every row,"
            " so narrow the query.",
        ),
        (
            "SELECT * FROM v_shots WHERE player = 'Nobody'",
            True,
            0,
            "The query returned no rows, so there is no chart.",
        ),
        (
            "SELECT x, y FROM v_shots",
            True,
            2,
            "A shot_map chart needs the columns x, y, xg, outcome, minute, opponent."
            " Missing: xg, outcome, minute, opponent.",
        ),
        (
            f"SELECT {SHOT.replace('0.25', '1.5')}",
            True,
            1,
            "Row 1, column xg:",
        ),
    ],
)
def test_build_chart_gives_the_reason_and_no_chart(seeded, sql, ran, rows, reason):
    result = tools.build_chart("shot_map", sql, "Henry")

    assert not result.ok and result.chart is None
    assert result.error.startswith(reason)
    assert re.fullmatch(r"q_[0-9a-f]{8}", result.call_id)
    assert (result.sql is not None) == ran
    assert result.row_count == rows


def test_build_chart_reports_a_database_it_cannot_reach_as_text(no_database):
    result = tools.build_chart("shot_map", "SELECT * FROM v_shots", "Henry")

    assert (result.ok, result.chart) == (False, None)
    assert result.error == "The database is not reachable."
    assert result.sql == f"SELECT * FROM v_shots LIMIT {MAX_ROWS}"


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
