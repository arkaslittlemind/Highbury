import psycopg
import pytest

VIEWS = ["v_matches", "v_shots", "v_player_match", "v_player_season", "v_passes"]


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


def insert_shot(conn, ids, *, x=108.0, y=40.0, xg=0.3, outcome="goal", source_id="s1"):
    conn.execute(
        "INSERT INTO shots (match_id, player_id, team_id, minute, x, y, xg, outcome, source,"
        " source_shot_id) VALUES (%s, %s, %s, 27, %s, %s, %s, %s, 'statsbomb', %s)",
        (ids["match"], ids["player"], ids["home"], x, y, xg, outcome, source_id),
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


def test_all_five_views_exist(conn):
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
    for event_type, source_id in [("pass", "e1"), ("carry", "e2")]:
        conn.execute(
            "INSERT INTO events (match_id, player_id, team_id, type, minute, second,"
            " source_event_id) VALUES (%s, %s, %s, %s, 1, 0, %s)",
            (ids["match"], ids["player"], ids["home"], event_type, source_id),
        )

    rows = conn.execute("SELECT player, recipient, opponent FROM v_passes").fetchall()

    assert rows == [("Thierry Henry", None, "Leeds")]
