from dataclasses import replace
from datetime import date

import pytest

from ingest import load, migrate


def shot(source_id, match, player, team, outcome, xg):
    return load.ShotRow(
        source_id=source_id,
        match=match,
        player=player,
        team=team,
        minute=12,
        x=104.0,
        y=36.0,
        xg=xg,
        outcome=outcome,
        body_part="right foot",
        situation="open play",
    )


def stat(player, match, team, minutes, goals=0, assists=0, xg=0.0, xa=0.0):
    return load.StatRow(player, match, team, minutes, goals, assists, xg, xa)


def two_matches() -> load.SeasonRows:
    """Arsenal 2-1 Everton at home, then Chelsea 1-1 Arsenal away."""
    return load.SeasonRows(
        season_id=2003,
        season_label="2003-04",
        data_level="EVENT",
        source="statsbomb",
        teams=["Arsenal", "Chelsea", "Everton"],
        players=[
            load.PlayerRow("10", "Thierry Henry", "Thierry Henry", "Left Center Forward"),
            load.PlayerRow("11", "Robert Pires", "Robert Pires", "Left Midfield"),
            load.PlayerRow("20", "Wayne Rooney", "Wayne Mark Rooney", "Center Forward"),
        ],
        matches=[
            load.MatchRow("100", date(2003, 8, 16), "Arsenal", "Everton", 2, 1, "Arsenal Stadium"),
            load.MatchRow("101", date(2003, 10, 18), "Chelsea", "Arsenal", 1, 1, None),
        ],
        shots=[
            shot("s1", "100", "10", "Arsenal", "goal", 0.25),
            shot("s2", "100", "10", "Arsenal", "saved", 0.1),
            shot("s3", "100", "20", "Everton", "goal", 0.5),
            shot("s4", "101", "10", "Arsenal", "goal", 0.75),
        ],
        events=[
            load.EventRow(
                "p1", "100", "11", "Arsenal", "pass", 12, 30, 80.0, 20.0, 100.0, 35.0,
                None, True, 7, "10", 1,
            ),
            load.EventRow(
                "p2", "100", "20", "Everton", "pass", 30, 5, 40.0, 40.0, 120.0, 80.0,
                "incomplete", False, 21, None, 2,
            ),
            load.EventRow(
                "c1", "100", "10", "Arsenal", "carry", 12, 33, 50.0, 30.0, 58.0, 33.0,
                None, False, 7, None,
            ),
            load.EventRow(
                "pr1", "101", "10", "Arsenal", "pressure", 70, 0, 70.0, 10.0, None, None,
                None, False, 90, None,
            ),
        ],
        stats=[
            stat("10", "100", "Arsenal", 90, goals=1, xg=0.35),
            stat("11", "100", "Arsenal", 60, assists=1, xa=0.25),
            stat("20", "100", "Everton", 90, goals=1, xg=0.5),
            stat("10", "101", "Arsenal", 75, goals=1, xg=0.75),
        ],
    )  # fmt: skip


def ids(conn, table):
    return conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()


def test_a_load_writes_every_row(ingest):
    load.load(ingest, two_matches())

    assert load.table_counts(ingest) == {
        "seasons": 1,
        "teams": 3,
        "players": 3,
        "player_aliases": 3,
        "matches": 2,
        "shots": 4,
        "events": 4,
        "player_match_stats": 4,
    }


def test_a_second_load_changes_no_row_count_and_no_id(ingest):
    load.load(ingest, two_matches())
    counts = load.table_counts(ingest)
    matches, players, teams = ids(ingest, "matches"), ids(ingest, "players"), ids(ingest, "teams")

    load.load(ingest, two_matches())

    assert load.table_counts(ingest) == counts
    assert ids(ingest, "matches") == matches
    assert ids(ingest, "players") == players
    assert ids(ingest, "teams") == teams


def test_the_details_of_a_pass_a_duel_and_an_aerial_win_are_stored_and_updated(ingest):
    rows = two_matches()
    rows.events[0] = replace(
        rows.events[0], pass_length=40.5, pass_type="throw-in", shot_assist=True, aerial_won=True
    )
    rows.events.append(
        load.EventRow(
            "d1", "100", "20", "Everton", "duel", 40, 0, 60.0, 40.0, None, None,
            "won", False, 30, None, 1, duel_type="tackle",
        )
    )  # fmt: skip
    rows.shots[0] = replace(rows.shots[0], aerial_won=True)
    load.load(ingest, rows)

    def details():
        return ingest.execute(
            "SELECT source_event_id, pass_length, pass_type, shot_assist, goal_assist,"
            " aerial_won, duel_type FROM events WHERE source_event_id IN ('p1', 'd1', 'c1')"
            " ORDER BY source_event_id"
        ).fetchall()

    assert details() == [
        ("c1", None, None, False, False, False, None),
        ("d1", None, None, False, False, False, "tackle"),
        ("p1", 40.5, "throw-in", True, False, True, None),
    ]
    assert ingest.execute("SELECT source_shot_id FROM shots WHERE aerial_won").fetchall() == [
        ("s1",)
    ]

    # A second load takes the new values from the source.
    rows.events[0] = replace(rows.events[0], pass_type=None, goal_assist=True)
    load.load(ingest, rows)

    assert details()[2] == ("p1", 40.5, None, True, True, True, None)


def test_a_second_load_takes_changed_values_from_the_source(ingest):
    load.load(ingest, two_matches())
    rows = two_matches()
    rows.matches[1] = load.MatchRow("101", date(2003, 10, 18), "Chelsea", "Arsenal", 1, 2, None)
    rows.stats[3] = stat("10", "101", "Arsenal", 75, goals=2, xg=0.75)

    load.load(ingest, rows)

    assert ingest.execute(
        "SELECT away_goals FROM matches WHERE source_match_id = '101'"
    ).fetchone() == (2,)
    assert ingest.execute("SELECT sum(goals) FROM player_match_stats").fetchone() == (4,)


def test_the_analyst_reads_the_loaded_season_through_the_views(ingest, analyst):
    # Loaded twice: a row that a second run duplicated would show up in the views.
    load.load(ingest, two_matches())
    load.load(ingest, two_matches())
    ingest.commit()

    assert analyst.execute(
        "SELECT season, home_team, away_team, home_goals, away_goals, venue"
        " FROM v_matches ORDER BY match_date"
    ).fetchall() == [
        ("2003-04", "Arsenal", "Everton", 2, 1, "Arsenal Stadium"),
        ("2003-04", "Chelsea", "Arsenal", 1, 1, None),
    ]
    assert analyst.execute(
        "SELECT player, team, opponent, outcome, is_goal, source FROM v_shots"
        " WHERE is_goal ORDER BY match_date, team"
    ).fetchall() == [
        ("Thierry Henry", "Arsenal", "Everton", "goal", True, "statsbomb"),
        ("Wayne Rooney", "Everton", "Arsenal", "goal", True, "statsbomb"),
        ("Thierry Henry", "Arsenal", "Chelsea", "goal", True, "statsbomb"),
    ]
    assert analyst.execute(
        "SELECT opponent, minutes, goals FROM v_player_match"
        " WHERE player = 'Thierry Henry' ORDER BY match_date"
    ).fetchall() == [("Everton", 90, 1), ("Chelsea", 75, 1)]
    assert analyst.execute(
        "SELECT matches, minutes, goals, assists, shots FROM v_player_season"
        " WHERE player = 'Thierry Henry' AND season = '2003-04'"
    ).fetchone() == (2, 165, 2, 0, 3)
    assert analyst.execute(
        "SELECT player, recipient, team, opponent, outcome, under_pressure, period"
        " FROM v_passes ORDER BY minute"
    ).fetchall() == [
        ("Robert Pires", "Thierry Henry", "Arsenal", "Everton", None, True, 1),
        ("Wayne Rooney", None, "Everton", "Arsenal", "incomplete", False, 2),
    ]


def test_the_ingest_url_comes_from_the_environment():
    url = "postgresql://ingest:secret@localhost:5433/highbury"

    assert load.ingest_url({"INGEST_DATABASE_URL": url}) == url


def test_a_missing_ingest_url_names_the_variable():
    with pytest.raises(migrate.SettingsError, match="INGEST_DATABASE_URL"):
        load.ingest_url({})


TWO_MATCH_FACTS = load.SeasonFacts(
    season="2003-04",
    team="Arsenal",
    matches=2,
    wins=1,
    draws=1,
    losses=0,
    points=4,
    goals_for=3,
    top_scorer="Thierry Henry",
    top_scorer_goals=2,
)


def test_a_season_that_matches_its_facts_passes_the_check(ingest):
    load.load(ingest, two_matches())

    load.check_season(ingest, TWO_MATCH_FACTS)


def test_a_season_that_differs_from_its_facts_names_every_mismatch(ingest):
    load.load(ingest, two_matches())
    invincibles = replace(
        TWO_MATCH_FACTS, matches=38, wins=26, draws=12, points=90, top_scorer_goals=30
    )

    with pytest.raises(load.SanityError) as error:
        load.check_season(ingest, invincibles)

    message = str(error.value)
    assert "matches: expected 38, found 2" in message
    assert "wins: expected 26, found 1" in message
    assert "draws: expected 12, found 1" in message
    assert "points: expected 90, found 4" in message
    assert "Thierry Henry goals: expected 30, found 2" in message
    # Losses match, so they are not reported.
    assert "losses" not in message


def test_an_empty_season_fails_the_check(ingest):
    with pytest.raises(load.SanityError, match="matches: expected 2, found 0"):
        load.check_season(ingest, TWO_MATCH_FACTS)


def test_a_wrong_team_goal_total_fails_the_check(ingest):
    load.load(ingest, two_matches())

    with pytest.raises(load.SanityError, match="goals for: expected 73, found 3"):
        load.check_season(ingest, replace(TWO_MATCH_FACTS, goals_for=73))
