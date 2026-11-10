"""The rules of v_player_similarity, on small hand-written seasons."""

import math
import statistics
from datetime import date, timedelta

import pytest

from ingest import load

MATCHES = [str(100 + n) for n in range(10)]
FIRST_DAY = date(2003, 8, 16)


def rounded_distances(counts: dict[str, dict[str, float]], minutes: int) -> dict:
    """The distance of each ordered pair, computed here and not by the view.

    Each count becomes a per-90 rate, each rate a z-score among the players, with 0 for a
    metric that has no spread. The distance is Euclidean over the z-scores.
    """
    metrics = next(iter(counts.values())).keys()
    z = {player: {} for player in counts}
    for metric in metrics:
        rates = {player: counts[player][metric] * 90 / minutes for player in counts}
        mean = statistics.fmean(rates.values())
        spread = statistics.pstdev(rates.values())
        for player, rate in rates.items():
            z[player][metric] = (rate - mean) / spread if spread else 0.0
    return {
        (a, b): round(math.dist(list(z[a].values()), list(z[b].values())), 2)
        for a in counts
        for b in counts
        if a != b
    }


def rows_of(analyst, season):
    return analyst.execute(
        "SELECT player, team, minutes, similar_player, rank, distance, metrics"
        " FROM v_player_similarity WHERE season = %s ORDER BY player, rank",
        (season,),
    ).fetchall()


def event(source_id, player, kind, outcome=None, **details):
    return load.EventRow(
        source_id, MATCHES[0], player, "Arsenal", kind, 10, 0, 60.0, 40.0, None, None,
        outcome, False, 1, None, 1, **details,
    )  # fmt: skip


def stats(player, team, matches, goals=0, xg=0.0):
    """90 minutes in each match. The goals and the xG count in the first match only."""
    return [
        load.StatRow(player, match, team, 90, goals if n == 0 else 0, 0, xg if n == 0 else 0.0, 0)
        for n, match in enumerate(matches)
    ]


def match_rows(first_day: date, opponent: str) -> list[load.MatchRow]:
    """Arsenal at home in each match of MATCHES, one week apart."""
    return [
        load.MatchRow(match, first_day + timedelta(days=7 * n), "Arsenal", opponent, 1, 0, None)
        for n, match in enumerate(MATCHES)
    ]


def henry_shot(n: int) -> load.ShotRow:
    return load.ShotRow(
        f"s{n}", MATCHES[0], "3", "Arsenal", 20, 110.0, 40.0, 0.3, "goal", None, None
    )


def season_2003() -> load.SeasonRows:
    """Ten Arsenal-Everton matches.

    Vieira, Pires, and Henry play 900 minutes. Keown plays 810, under the rule. Rooney
    plays 900 for Everton, and 2003-04 compares Arsenal players only. Nobody makes an
    aerial win or a long ball, so those two metrics have no spread.
    """
    return load.SeasonRows(
        season_id=2003,
        season_label="2003-04",
        data_level="EVENT",
        source="statsbomb",
        teams=["Arsenal", "Everton"],
        players=[
            load.PlayerRow("1", "Patrick Vieira", "Patrick Vieira", None),
            load.PlayerRow("2", "Robert Pirès", "Robert Pirès", None),
            load.PlayerRow("3", "Thierry Henry", "Thierry Henry", None),
            load.PlayerRow("4", "Martin Keown", "Martin Keown", None),
            load.PlayerRow("5", "Wayne Rooney", "Wayne Rooney", None),
        ],
        matches=match_rows(FIRST_DAY, "Everton"),
        shots=[henry_shot(n) for n in range(3)],
        events=[
            event("t1", "1", "duel", outcome="won", duel_type="tackle"),
            event("t2", "1", "duel", outcome="won", duel_type="tackle"),
            event("p1", "1", "pass", pass_length=10.0),
            event("p2", "1", "pass", pass_length=12.0),
            event("p3", "2", "pass", pass_length=15.0, shot_assist=True),
            event("p4", "2", "pass", pass_length=8.0, goal_assist=True),
            event("p5", "3", "pass", pass_length=9.0),
        ],
        stats=[
            *stats("1", "Arsenal", MATCHES),
            *stats("2", "Arsenal", MATCHES, goals=1, xg=0.2),
            *stats("3", "Arsenal", MATCHES, goals=2, xg=0.9),
            *stats("4", "Arsenal", MATCHES[:9]),
            *stats("5", "Everton", MATCHES, goals=3, xg=1.5),
        ],
    )  # fmt: skip


def load_committed(conn, rows):
    # Only analyst_ro can read the view, and it sees committed rows only.
    load.load(conn, rows)
    conn.commit()


def test_the_2003_04_distance_follows_its_definition(ingest, analyst):
    load_committed(ingest, season_2003())
    counts = {
        # chances, duels won, aerials won, passes completed, long balls, goals, shots, xG
        "Patrick Vieira": [0, 2, 0, 2, 0, 0, 0, 0.0],
        "Robert Pirès": [2, 0, 0, 2, 0, 1, 0, 0.2],
        "Thierry Henry": [0, 0, 0, 1, 0, 2, 3, 0.9],
    }
    expected = rounded_distances(
        {player: dict(enumerate(values)) for player, values in counts.items()}, 900
    )

    rows = rows_of(analyst, "2003-04")

    assert {
        (player, similar): float(distance) for player, _, _, similar, _, distance, _ in rows
    } == (expected)
    assert {row[6] for row in rows} == {8}
    assert {row[1] for row in rows} == {"Arsenal"}
    assert {row[2] for row in rows} == {900}


def test_the_rank_orders_by_distance_and_skips_the_player_himself(ingest, analyst):
    load_committed(ingest, season_2003())

    rows = rows_of(analyst, "2003-04")

    assert all(player != similar for player, _, _, similar, _, _, _ in rows)
    for player in {row[0] for row in rows}:
        own = [row for row in rows if row[0] == player]
        assert [row[4] for row in own] == [1, 2]
        assert own[0][5] <= own[1][5]


def test_a_player_under_900_minutes_and_an_opponent_are_left_out(ingest, analyst):
    load_committed(ingest, season_2003())

    names = {name for row in rows_of(analyst, "2003-04") for name in (row[0], row[3])}

    assert names == {"Patrick Vieira", "Robert Pirès", "Thierry Henry"}


def fpl_row(player_id, match_id, team_id, gameweek, goals=0, assists=0, tackles=0, saves=0):
    return (
        player_id, match_id, team_id, gameweek, 90, goals, assists, False, saves, 0, 0, 0, 0,
        0, 0, 5.0, tackles, 0, 0,
    )  # fmt: skip


def load_fpl_2025(conn):
    """Ten Arsenal-Chelsea matches with FPL rows for three players.

    Rice plays every match for Arsenal, Raya keeps goal for Arsenal, and Madueke plays
    five matches for Tottenham and then five for Chelsea.
    """
    rows = load.SeasonRows(
        season_id=2025,
        season_label="2025-26",
        data_level="SHOT",
        source="understat",
        teams=["Arsenal", "Chelsea", "Tottenham"],
        players=[
            load.PlayerRow("1", "Declan Rice", "Declan Rice", None),
            load.PlayerRow("2", "David Raya", "David Raya", None),
            load.PlayerRow("3", "Noni Madueke", "Noni Madueke", None),
        ],
        matches=match_rows(date(2025, 8, 16), "Chelsea"),
        shots=[],
        events=[],
        stats=[],
    )  # fmt: skip
    load.load(conn, rows)
    ids = dict(conn.execute("SELECT name, id FROM players").fetchall())
    teams = dict(conn.execute("SELECT name, id FROM teams").fetchall())
    matches = [
        row[0]
        for row in conn.execute(
            "SELECT m.id FROM matches m JOIN seasons s ON s.id = m.season_id"
            " WHERE s.label = '2025-26' ORDER BY m.match_date"
        ).fetchall()
    ]
    fpl = []
    for week, match in enumerate(matches, start=1):
        fpl.append(fpl_row(ids["Declan Rice"], match, teams["Arsenal"], week, tackles=3))
        fpl.append(fpl_row(ids["David Raya"], match, teams["Arsenal"], week, saves=4))
        club = teams["Tottenham"] if week <= 5 else teams["Chelsea"]
        fpl.append(fpl_row(ids["Noni Madueke"], match, club, week, goals=week % 2))
    conn.cursor().executemany(
        "INSERT INTO fpl_player_match (player_id, match_id, team_id, gameweek, minutes, goals,"
        " assists, clean_sheet, saves, bonus, bps, yellow_cards, red_cards,"
        " defensive_contribution, points, price, tackles, recoveries,"
        " clearances_blocks_interceptions)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        fpl,
    )
    conn.commit()


def test_the_2025_26_distance_uses_the_six_fpl_metrics(ingest, analyst):
    load_fpl_2025(ingest)
    counts = {
        # goals, assists, tackles, recoveries, CBI, saves
        "Declan Rice": [0, 0, 30, 0, 0, 0],
        "David Raya": [0, 0, 0, 0, 0, 40],
        "Noni Madueke": [5, 0, 0, 0, 0, 0],
    }
    expected = rounded_distances(
        {player: dict(enumerate(values)) for player, values in counts.items()}, 900
    )

    rows = rows_of(analyst, "2025-26")

    assert {
        (player, similar): float(distance) for player, _, _, similar, _, distance, _ in rows
    } == (expected)
    assert {row[6] for row in rows} == {6}


def test_a_transfer_shows_the_club_of_the_last_match(ingest, analyst):
    load_fpl_2025(ingest)

    teams = {row[0]: (row[1], row[2]) for row in rows_of(analyst, "2025-26")}

    assert teams["Noni Madueke"] == ("Chelsea", 900)


def test_the_two_seasons_never_share_a_pair(ingest, analyst):
    load_committed(ingest, season_2003())
    load_fpl_2025(ingest)

    mixed = analyst.execute(
        "SELECT count(*) FROM v_player_similarity s"
        " JOIN v_player_similarity t ON t.season <> s.season AND t.player = s.similar_player"
    ).fetchone()

    assert mixed == (0,)
    assert len(rows_of(analyst, "2003-04")) == 6
    assert len(rows_of(analyst, "2025-26")) == 6


@pytest.mark.parametrize("season", ["2003-04", "2025-26"])
def test_an_empty_season_has_no_row(analyst, season):
    assert rows_of(analyst, season) == []
