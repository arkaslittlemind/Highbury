import psycopg
import pytest

VIEWS = [
    "v_matches",
    "v_shots",
    "v_player_match",
    "v_player_season",
    "v_passes",
    "v_substitutions",
]


@pytest.fixture
def conn(db):
    """Admin connection whose changes are rolled back after the test."""
    with psycopg.connect(db.admin_url) as connection:
        yield connection
        connection.rollback()


def insert_match(conn) -> dict[str, int]:
    conn.execute("INSERT INTO seasons VALUES (2003, '2003-04', 'EVENT')")
    home = conn.execute("INSERT INTO teams (name) VALUES ('Arsenal') RETURNING id").fetchone()[0]
    away = conn.execute("INSERT INTO teams (name) VALUES ('Leeds') RETURNING id").fetchone()[0]
    player = conn.execute(
        "INSERT INTO players (name) VALUES ('Thierry Henry') RETURNING id"
    ).fetchone()[0]
    match = conn.execute(
        "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id, home_goals,"
        " away_goals, source, source_match_id)"
        " VALUES (2003, '2004-04-16', %s, %s, 5, 0, 'statsbomb', 'm1') RETURNING id",
        (home, away),
    ).fetchone()[0]
    return {"home": home, "away": away, "player": player, "match": match}


def insert_shot(conn, ids, *, x=108.0, y=40.0, xg=0.3, outcome="goal", source_id="s1", team="home"):
    conn.execute(
        "INSERT INTO shots (match_id, player_id, team_id, minute, x, y, xg, outcome, source,"
        " source_shot_id) VALUES (%s, %s, %s, 27, %s, %s, %s, %s, 'statsbomb', %s)",
        (ids["match"], ids["player"], ids[team], x, y, xg, outcome, source_id),
    )


def insert_event(conn, ids, *, event_type="pass", source_id="e1", team="home", **position):
    coords = {"x": None, "y": None, "end_x": None, "end_y": None} | position
    conn.execute(
        "INSERT INTO events (match_id, player_id, team_id, type, minute, second, x, y, end_x,"
        " end_y, source_event_id) VALUES (%s, %s, %s, %s, 1, 0, %s, %s, %s, %s, %s)",
        (ids["match"], ids["player"], ids[team], event_type, *coords.values(), source_id),
    )


@pytest.mark.parametrize("view", VIEWS)
def test_view_selects_on_empty_database(conn, view):
    assert conn.execute(f"SELECT * FROM {view}").fetchall() == []


def test_every_view_column_has_a_comment(conn):
    missing = conn.execute(
        """
        SELECT c.relname, a.attname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public' AND c.relkind = 'v' AND a.attnum > 0
          AND col_description(c.oid, a.attnum) IS NULL
        """
    ).fetchall()

    assert missing == []


def test_all_six_views_exist(conn):
    rows = conn.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public'")

    assert sorted(row[0] for row in rows) == sorted(VIEWS)


@pytest.mark.parametrize("field", ["x", "y", "xg"])
def test_shot_rejects_out_of_range_values(conn, field):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        insert_shot(conn, ids, **{field: 121.0})


def test_shot_source_id_is_unique_per_source(conn):
    ids = insert_match(conn)
    insert_shot(conn, ids)

    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_shot(conn, ids)


def test_season_rejects_unknown_data_level(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO seasons VALUES (2025, '2025-26', 'PARTIAL')")


def test_shot_view_names_the_opponent_and_flags_goals(conn):
    ids = insert_match(conn)
    insert_shot(conn, ids, outcome="goal", source_id="s1")
    insert_shot(conn, ids, outcome="saved", source_id="s2")

    rows = conn.execute(
        "SELECT season, player, team, opponent, is_goal FROM v_shots ORDER BY is_goal DESC"
    ).fetchall()

    assert rows == [
        ("2003-04", "Thierry Henry", "Arsenal", "Leeds", True),
        ("2003-04", "Thierry Henry", "Arsenal", "Leeds", False),
    ]


def test_player_season_view_totals_stats_and_shots(conn):
    ids = insert_match(conn)
    insert_shot(conn, ids, source_id="s1")
    insert_shot(conn, ids, source_id="s2")
    conn.execute(
        "INSERT INTO player_match_stats (player_id, match_id, team_id, minutes, goals, assists)"
        " VALUES (%s, %s, %s, 90, 4, 0)",
        (ids["player"], ids["match"], ids["home"]),
    )

    row = conn.execute(
        "SELECT player, season, matches, minutes, goals, shots FROM v_player_season"
    ).fetchone()

    assert row == ("Thierry Henry", "2003-04", 1, 90, 4, 2)


def test_passes_view_holds_only_pass_events(conn):
    ids = insert_match(conn)
    insert_event(conn, ids, event_type="pass", source_id="e1")
    insert_event(conn, ids, event_type="carry", source_id="e2")

    rows = conn.execute("SELECT player, recipient, opponent FROM v_passes").fetchall()

    assert rows == [("Thierry Henry", None, "Leeds")]


def test_substitutions_view_names_the_player_off_the_player_on_and_the_reason(conn):
    ids = insert_match(conn)
    on = conn.execute("INSERT INTO players (name) VALUES ('Edu') RETURNING id").fetchone()[0]
    conn.execute(
        "INSERT INTO events (match_id, player_id, team_id, type, period, minute, second,"
        " outcome, recipient_id, source_event_id)"
        " VALUES (%s, %s, %s, 'substitution', 2, 45, 0, 'tactical', %s, 'sub1')",
        (ids["match"], ids["player"], ids["home"], on),
    )

    rows = conn.execute(
        "SELECT player_off, player_on, reason, period, minute, second FROM v_substitutions"
    ).fetchall()

    assert rows == [("Thierry Henry", "Edu", "tactical", 2, 45, 0)]


def test_an_event_period_outside_the_match_is_rejected(conn):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO events (match_id, team_id, type, period, minute, second,"
            " source_event_id) VALUES (%s, %s, 'pass', 6, 1, 0, 'e1')",
            (ids["match"], ids["home"]),
        )


def test_substitutions_view_holds_only_substitution_events(conn):
    ids = insert_match(conn)
    insert_event(conn, ids, event_type="pass", source_id="e1")
    insert_event(conn, ids, event_type="substitution", source_id="e2")

    rows = conn.execute(
        "SELECT season, team, opponent, minute, second, player_off FROM v_substitutions"
    ).fetchall()

    assert rows == [("2003-04", "Arsenal", "Leeds", 1, 0, "Thierry Henry")]


def test_shot_rejects_an_outcome_that_is_not_lowercase(conn):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        insert_shot(conn, ids, outcome="Goal")


def test_event_rejects_a_type_that_is_not_lowercase(conn):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        insert_event(conn, ids, event_type="Pass")


@pytest.mark.parametrize(
    ("field", "value"), [("x", 121), ("y", 81), ("end_x", -1), ("end_y", 80.5)]
)
def test_event_rejects_positions_outside_the_pitch(conn, field, value):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.CheckViolation):
        insert_event(conn, ids, **{field: value})


def test_event_source_id_is_unique(conn):
    ids = insert_match(conn)
    insert_event(conn, ids)

    with pytest.raises(psycopg.errors.UniqueViolation):
        insert_event(conn, ids)


def test_match_source_id_is_unique_per_source(conn):
    ids = insert_match(conn)

    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id, home_goals,"
            " away_goals, source, source_match_id)"
            " VALUES (2003, '2004-05-15', %s, %s, 2, 1, 'statsbomb', 'm1')",
            (ids["home"], ids["away"]),
        )


def test_alias_name_is_unique_per_source(conn):
    ids = insert_match(conn)
    alias = (
        "INSERT INTO player_aliases (player_id, source, source_name) VALUES (%s, 'manual', 'Titi')"
    )
    conn.execute(alias, (ids["player"],))

    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(alias, (ids["player"],))


def test_shot_view_names_the_home_team_as_opponent_for_an_away_shot(conn):
    ids = insert_match(conn)
    insert_shot(conn, ids, team="away")

    assert conn.execute("SELECT team, opponent FROM v_shots").fetchall() == [("Leeds", "Arsenal")]


def test_passes_view_names_the_home_team_as_opponent_for_an_away_pass(conn):
    ids = insert_match(conn)
    insert_event(conn, ids, team="away")

    assert conn.execute("SELECT team, opponent FROM v_passes").fetchall() == [("Leeds", "Arsenal")]


def test_matches_view_shows_names_and_score(conn):
    insert_match(conn)

    row = conn.execute(
        "SELECT season, match_date::text, home_team, away_team, home_goals, away_goals"
        " FROM v_matches"
    ).fetchone()

    assert row == ("2003-04", "2004-04-16", "Arsenal", "Leeds", 5, 0)


@pytest.mark.parametrize(
    ("team", "expected"), [("home", ("Arsenal", "Leeds")), ("away", ("Leeds", "Arsenal"))]
)
def test_player_match_view_names_team_and_opponent(conn, team, expected):
    ids = insert_match(conn)
    conn.execute(
        "INSERT INTO player_match_stats (player_id, match_id, team_id, minutes, goals)"
        " VALUES (%s, %s, %s, 90, 1)",
        (ids["player"], ids["match"], ids[team]),
    )

    row = conn.execute(
        "SELECT player, team, opponent, minutes, goals FROM v_player_match"
    ).fetchone()

    assert row == ("Thierry Henry", *expected, 90, 1)
