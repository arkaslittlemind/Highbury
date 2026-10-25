import csv
import io
from dataclasses import replace
from decimal import Decimal

import httpx
import psycopg
import pytest

from ingest import command, fpl, load
from ingest.fpl import FplRow, FplSeason
from ingest.overrides import PlayerOverride

TEAMS = {"Man Utd": "Manchester United"}
# id, FPL name. Ids 1 to 3 are the clubs the tests use; the rest fill the league.
FPL_TEAMS = [("1", "Arsenal"), ("2", "Everton"), ("3", "Man Utd")]
GW_HEADER = ["name", "position", "team", "xP", *fpl.GW_COLUMNS[3:], "element", "GW"]


def table(header: list[str], rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def gw_row(**cells) -> dict:
    row = {column: "0" for column in GW_HEADER}
    row |= {
        "name": "Bukayo Saka",
        "position": "MID",
        "team": "Arsenal",
        "xP": "5.5",
        "element": "16",
        "fixture": "1",
        "GW": "1",
        "minutes": "90",
        "goals_scored": "1",
        "assists": "1",
        "clean_sheets": "1",
        "bonus": "3",
        "bps": "41",
        "defensive_contribution": "7",
        "total_points": "15",
        "value": "105",
    }
    return row | cells


# Fixture 1: Arsenal v Everton in GW 1. Fixture 2: Man Utd v Arsenal in GW 2.
FIXTURES = [
    {"id": "1", "event": "1", "team_h": "1", "team_a": "2", "stats": "[]"},
    {"id": "2", "event": "2", "team_h": "3", "team_a": "1", "stats": "[]"},
]


def files(gw_rows: list[dict], fixtures: list[dict] = FIXTURES) -> tuple[str, str, str]:
    return (
        table(GW_HEADER, gw_rows),
        table(["id", "event", "team_h", "team_a", "stats"], fixtures),
        table(
            ["id", "name", "short_name"],
            [{"id": i, "name": n, "short_name": n[:3]} for i, n in FPL_TEAMS],
        ),
    )


def parse(gw_rows: list[dict], fixtures: list[dict] = FIXTURES) -> FplSeason:
    return fpl.parse(*files(gw_rows, fixtures), TEAMS)


def test_a_row_becomes_an_fpl_row_with_canonical_names():
    season = parse([gw_row(), gw_row(fixture="2", GW="2", team="Arsenal", value="104")])

    assert season.players == [load.PlayerRow("16", "Bukayo Saka", "Bukayo Saka", None)]
    assert season.rows[0] == FplRow(
        player="16",
        team="Arsenal",
        home_team="Arsenal",
        away_team="Everton",
        gameweek=1,
        minutes=90,
        goals=1,
        assists=1,
        clean_sheet=True,
        saves=0,
        bonus=3,
        bps=41,
        yellow_cards=0,
        red_cards=0,
        defensive_contribution=7,
        points=15,
        price=Decimal("10.5"),
    )
    assert (season.rows[1].home_team, season.rows[1].gameweek) == ("Manchester United", 2)
    assert season.rows[1].price == Decimal("10.4")


def test_rows_with_no_minutes_are_dropped_with_their_players():
    season = parse([gw_row(), gw_row(element="99", name="Unused Sub", minutes="0")])

    assert [row.player for row in season.rows] == ["16"]
    assert [player.source_id for player in season.players] == ["16"]


def test_negative_bps_and_points_are_kept():
    (row,) = parse([gw_row(bps="-5", total_points="-2")]).rows

    assert (row.bps, row.points) == (-5, -2)


def test_an_identical_repeat_is_kept_once():
    assert len(parse([gw_row(), gw_row()]).rows) == 1


def test_a_repeat_that_differs_is_rejected():
    with pytest.raises(
        ValueError, match="line 3: player 16 has a second, different row for fixture 1"
    ):
        parse([gw_row(), gw_row(total_points="14")])


def test_a_missing_column_is_named():
    gw, fixtures, teams = files([gw_row()])

    with pytest.raises(
        ValueError, match="merged_gw.csv: the file has no column defensive_contribution"
    ):
        fpl.parse(gw.replace("defensive_contribution", "dc", 1), fixtures, teams, TEAMS)


@pytest.mark.parametrize(
    ("cells", "reason"),
    [
        ({"minutes": "x"}, "line 2: minutes is 'x', not a count"),
        ({"goals_scored": "-1"}, "line 2: goals_scored is '-1', not a count"),
        ({"saves": ""}, "line 2: saves is '', not a count"),
        ({"total_points": "1.5"}, "line 2: total_points is '1.5', not an integer"),
        ({"clean_sheets": "2"}, "line 2: clean_sheets is 2, not 0 or 1"),
        ({"value": "0"}, "line 2: value is 0, not a price"),
        ({"name": " "}, "line 2: name is empty"),
        ({"team": "Chelsea"}, "line 2: 'Chelsea' is not a side of fixture 1"),
        ({"fixture": "7"}, "line 2: fixture '7' is not in fixtures.csv"),
    ],
)
def test_a_bad_cell_names_its_line(cells, reason):
    with pytest.raises(ValueError, match=reason):
        parse([gw_row(**cells)])


def test_one_player_with_two_names_is_rejected():
    with pytest.raises(ValueError, match="player 16 is 'B. Saka' and 'Bukayo Saka'"):
        parse([gw_row(), gw_row(fixture="2", name="B. Saka")])


def test_a_fixture_with_no_gameweek_is_rejected_only_when_a_row_played_in_it():
    postponed = [FIXTURES[0], FIXTURES[1] | {"event": ""}]

    assert len(parse([gw_row()], postponed).rows) == 1
    with pytest.raises(ValueError, match="fixture 2 has no gameweek from 1 to 38"):
        parse([gw_row(fixture="2")], postponed)


def test_a_fixture_with_an_unknown_team_is_rejected():
    with pytest.raises(ValueError, match="fixtures.csv line 2: team_a '9' is not in teams.csv"):
        parse([gw_row()], [FIXTURES[0] | {"team_a": "9"}])


def test_a_cached_file_is_read_without_a_download(tmp_path):
    (tmp_path / "teams.csv").write_text("cached", encoding="utf-8")

    assert fpl.fetch_file(tmp_path, "teams.csv", pytest.fail) == "cached"


def test_a_failed_download_says_where_to_save_the_file(monkeypatch):
    def refuse(url, timeout):
        raise httpx.ConnectTimeout("no route")

    monkeypatch.setattr(fpl.httpx, "get", refuse)

    with pytest.raises(command.FetchError) as error:
        fpl.download("merged_gw.csv")

    assert "data/2025-26/gws/merged_gw.csv" in str(error.value)
    assert str(error.value).endswith("merged_gw.csv")
    assert "Save it by hand as" in str(error.value)


# The database half: 2025-26 as the understat and footballdata loaders leave it.

NAMES = ["Arsenal", "Everton", "Manchester United", *(f"Club {n:02}" for n in range(17))]
# (Understat id, name, team, goals) in Arsenal v Everton.
UNDERSTAT = [
    ("u1", "Bukayo Saka", "Arsenal", 1),
    ("u2", "William Saliba", "Arsenal", 0),
    ("u3", "Gabriel", "Arsenal", 0),
    ("u4", "Gabriel Martinelli", "Arsenal", 1),
    ("u5", "Jordan Pickford", "Everton", 0),
]


def seed(conn: psycopg.Connection, *, football_data: bool = True) -> None:
    conn.execute("INSERT INTO seasons VALUES (2025, '2025-26', 'SHOT')")
    ids = {
        name: conn.execute("INSERT INTO teams (name) VALUES (%s) RETURNING id", (name,)).fetchone()[
            0
        ]
        for name in NAMES
    }
    for home in NAMES:
        for away in NAMES:
            arsenal = "Arsenal" in (home, away)
            if home == away or not (arsenal or football_data):
                continue
            conn.execute(
                "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id,"
                " home_goals, away_goals, source, source_match_id)"
                " VALUES (2025, '2025-08-16', %s, %s, 2, 1, %s, %s)",
                (
                    ids[home],
                    ids[away],
                    "understat" if arsenal else "football-data",
                    f"{home}:{away}",
                ),
            )
    (match_id,) = conn.execute(
        "SELECT id FROM matches WHERE source_match_id = 'Arsenal:Everton'"
    ).fetchone()
    for source_id, name, team, goals in UNDERSTAT:
        (player_id,) = conn.execute(
            "INSERT INTO players (name) VALUES (%s) RETURNING id", (name,)
        ).fetchone()
        conn.execute(
            "INSERT INTO player_aliases (player_id, source, source_player_id, source_name)"
            " VALUES (%s, 'understat', %s, %s)",
            (player_id, source_id, name),
        )
        conn.execute(
            "INSERT INTO player_match_stats (player_id, match_id, team_id, minutes, goals)"
            " VALUES (%s, %s, %s, 90, %s)",
            (player_id, match_id, ids[team], goals),
        )


def row(player: str, team: str, home: str, away: str, goals: int = 0) -> FplRow:
    return FplRow(
        player, team, home, away, 1, 90, goals, 0, False, 0, 0, 10, 0, 0, 3, 2, Decimal("5.5")
    )


# (FPL id, name, team, goals) in Arsenal v Everton, as FPL names them.
FPL = [
    ("16", "Bukayo Saka", "Arsenal", 1),
    ("5", "William Saliba Fonseca", "Arsenal", 0),
    ("6", "Gabriel dos Santos Magalhães", "Arsenal", 0),
    ("7", "Gabriel Martinelli Silva", "Arsenal", 1),
    ("300", "Jordan Pickford", "Everton", 0),
]


def season(*extra: FplRow, players=FPL) -> FplSeason:
    rows = [row(pid, team, "Arsenal", "Everton", goals) for pid, _, team, goals in players]
    # A player of the main rows keeps his name in his extra rows.
    names = {r.player: f"Player {r.player}" for r in extra} | {
        pid: name for pid, name, _, _ in players
    }
    return FplSeason(
        [load.PlayerRow(pid, name, name, None) for pid, name in names.items()], [*rows, *extra]
    )


# Martinelli's FPL name is as close to Gabriel as to him, so it needs this override.
MARTINELLI = {("fpl", "7"): PlayerOverride("fpl", "7", "2025-26", "Gabriel Martinelli")}


def owner(conn, source_id: str) -> str:
    (name,) = conn.execute(
        "SELECT p.name FROM player_aliases a JOIN players p ON p.id = a.player_id"
        " WHERE a.source = 'fpl' AND a.source_player_id = %s",
        (source_id,),
    ).fetchone()
    return name


# The ingest role cannot read the agent's views, so the tests join the table themselves.
ROWS = (
    "SELECT p.name, t.name, f.gameweek, f.points, f.price FROM fpl_player_match f"
    " JOIN players p ON p.id = f.player_id JOIN teams t ON t.id = f.team_id"
)


def counts(conn) -> dict[str, int]:
    found = load.table_counts(conn)
    found["fpl_player_match"] = conn.execute("SELECT count(*) FROM fpl_player_match").fetchone()[0]
    return found


def test_players_link_by_name_within_the_team_and_the_rows_are_written(ingest):
    seed(ingest)

    lines, _, review = fpl.load_fpl(ingest, season(), MARTINELLI)

    assert [owner(ingest, pid) for pid, *_ in FPL] == [
        "Bukayo Saka",
        "William Saliba",
        "Gabriel",
        "Gabriel Martinelli",
        "Jordan Pickford",
    ]
    # Saka and Pickford are exact; Martinelli is an override; the fuzzy ones are listed.
    assert sorted(r.source_name for r in review) == [
        "Gabriel dos Santos Magalhães",
        "William Saliba Fonseca",
    ]
    assert counts(ingest)["fpl_player_match"] == 5
    assert ingest.execute(f"{ROWS} WHERE p.name = 'Bukayo Saka'").fetchone() == (
        "Bukayo Saka",
        "Arsenal",
        1,
        2,
        Decimal("5.5"),
    )
    assert (
        "FPL players with minutes: 5, 5 with an fpl alias, 5 linked to a player of another source"
        in lines
    )
    assert lines[-1] == (
        "source check: every player row of the 38 Understat matches is in both sources;"
        " 5 players have the same goals"
    )


def test_an_ambiguous_name_becomes_a_new_player_and_fails_both_checks(ingest):
    seed(ingest)

    with pytest.raises(fpl.SourceMismatch) as error:
        fpl.load_fpl(ingest, season(), {})

    assert str(error.value) == (
        "2 player rows of Arsenal's matches have no partner in the other source:"
        " Gabriel Martinelli Silva on 2025-08-16: no Understat row;"
        " Gabriel Martinelli on 2025-08-16: no FPL row."
        " FPL goals differ from Understat's for 2 players:"
        " Gabriel Martinelli: Understat 1, FPL 0; Gabriel Martinelli Silva: Understat 0, FPL 1"
    )
    ambiguous = [r for r in error.value.review if r.source_id == "7"]
    assert ambiguous[0].match.outcome == "ambiguous"


def test_a_missed_link_of_a_player_with_no_goals_fails_the_pair_check(ingest):
    seed(ingest)
    # Pickford's FPL name is too far from his Understat name to link, and he did not score.
    renamed = [
        entry if entry[0] != "300" else ("300", "J. P. Keeper", "Everton", 0) for entry in FPL
    ]

    with pytest.raises(fpl.SourceMismatch) as error:
        fpl.load_fpl(ingest, season(players=renamed), MARTINELLI)

    assert str(error.value) == (
        "2 player rows of Arsenal's matches have no partner in the other source:"
        " J. P. Keeper on 2025-08-16: no Understat row;"
        " Jordan Pickford on 2025-08-16: no FPL row"
    )


def test_an_unused_substitute_of_understat_needs_no_fpl_row(ingest):
    seed(ingest)
    ingest.execute("UPDATE player_match_stats SET minutes = 0 WHERE goals = 0 AND minutes = 90")
    played = [entry for entry in FPL if entry[3] > 0 or entry[0] == "16"]

    lines, _, _ = fpl.load_fpl(ingest, season(players=played), MARTINELLI)

    assert lines[-1].startswith("source check: every player row")


def test_a_known_goal_difference_passes_and_any_other_fails(ingest, monkeypatch):
    seed(ingest)
    scored = [entry if entry[0] != "16" else ("16", "Bukayo Saka", "Arsenal", 2) for entry in FPL]
    monkeypatch.setattr(fpl, "GOAL_DIFFERENCES", {"Bukayo Saka": 1})

    lines, _, _ = fpl.load_fpl(ingest, season(players=scored), MARTINELLI)

    assert lines[-1].endswith("5 players have the same goals, 1 of them with a known difference")
    # A difference that the list does not give is still a mismatch, also for a listed player.
    monkeypatch.setattr(fpl, "GOAL_DIFFERENCES", {"Bukayo Saka": 2})
    with pytest.raises(fpl.SourceMismatch, match="Bukayo Saka: Understat 1, FPL 2"):
        fpl.load_fpl(ingest, season(players=scored), MARTINELLI)


def test_the_madueke_goal_is_the_one_known_difference():
    assert fpl.GOAL_DIFFERENCES == {"Noni Madueke": 1}


def test_a_player_who_never_met_arsenal_is_new_and_not_reviewed(ingest):
    seed(ingest)
    elsewhere = row("400", "Club 00", "Club 00", "Club 01")

    lines, _, review = fpl.load_fpl(ingest, season(elsewhere), MARTINELLI)

    assert owner(ingest, "400") == "Player 400"
    assert all(r.source_id != "400" for r in review)
    assert (
        "FPL players with minutes: 6, 6 with an fpl alias, 5 linked to a player of another source"
        in lines
    )


def test_a_transfer_links_through_either_team(ingest):
    seed(ingest)
    # Pickford's later rows are for Club 00, after a move.
    moved = row("300", "Club 00", "Club 00", "Club 01")

    fpl.load_fpl(ingest, season(moved), MARTINELLI)

    assert owner(ingest, "300") == "Jordan Pickford"
    teams = ingest.execute(f"{ROWS} WHERE p.name = 'Jordan Pickford' ORDER BY t.name").fetchall()
    assert [team for _, team, *_ in teams] == ["Club 00", "Everton"]


def test_a_second_run_changes_nothing(ingest):
    seed(ingest)
    fpl.load_fpl(ingest, season(), MARTINELLI)
    before = (
        counts(ingest),
        ingest.execute("SELECT * FROM fpl_player_match ORDER BY 1, 2").fetchall(),
    )

    fpl.load_fpl(ingest, season(), MARTINELLI)

    assert (
        counts(ingest),
        ingest.execute("SELECT * FROM fpl_player_match ORDER BY 1, 2").fetchall(),
    ) == before


def test_the_load_stops_when_football_data_did_not_run(ingest):
    seed(ingest, football_data=False)

    with pytest.raises(load.SanityError) as error:
        fpl.load_fpl(ingest, season(), MARTINELLI)

    assert str(error.value) == (
        "2025-26 has 38 league matches, 38 of them from Understat, expected 380 and 38."
        " Load understat and footballdata first"
    )


def test_a_fixture_with_no_match_is_named(ingest):
    seed(ingest)
    # A club of 2003-04 is in teams but has no 2025-26 match.
    ingest.execute("INSERT INTO teams (name) VALUES ('Charlton Athletic')")
    stray = row("500", "Arsenal", "Arsenal", "Charlton Athletic")

    with pytest.raises(
        load.SanityError, match="2025-26 Arsenal v Charlton Athletic has 0 matches to link to"
    ):
        fpl.load_fpl(ingest, season(stray), MARTINELLI)


def test_a_team_that_is_not_in_teams_is_named(ingest):
    seed(ingest)
    stray = row("500", "Spurs", "Spurs", "Arsenal")

    with pytest.raises(ValueError, match="no team named Spurs in teams"):
        fpl.load_fpl(ingest, season(stray), MARTINELLI)


def test_a_failed_goals_check_loads_nothing_and_still_writes_the_report(
    ingest, db, tmp_path, capsys, monkeypatch
):
    # The shipped FPL overrides name players that this database does not have.
    shipped = fpl.overrides.read()
    monkeypatch.setattr(fpl.overrides, "read", lambda: replace(shipped, players={}))
    seed(ingest)
    ingest.commit()
    before = counts(ingest)

    code = fpl.run(lambda: season(), {"INGEST_DATABASE_URL": db.ingest_url}, tmp_path)

    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("Sanity check failed, nothing was loaded: 2 player rows")
    assert "FPL goals differ from Understat's for 2 players" in err
    assert "review: 3 records to check in" in err
    assert counts(ingest) == before
    report = (tmp_path / "fpl.md").read_text(encoding="utf-8")
    assert "| 7 | Gabriel Martinelli Silva | Arsenal | ambiguous: new player |" in report


def test_a_successful_run_prints_the_counts_and_writes_the_report(
    ingest, db, tmp_path, capsys, monkeypatch
):
    seed(ingest)
    ingest.commit()
    shipped = fpl.overrides.read()
    monkeypatch.setattr(fpl.overrides, "read", lambda: replace(shipped, players=MARTINELLI))

    code = fpl.run(lambda: season(), {"INGEST_DATABASE_URL": db.ingest_url}, tmp_path)

    assert code == 0
    out = capsys.readouterr().out.splitlines()
    assert "fpl_player_match: 5" in out
    assert out[-1].startswith("review: 2 records to check in")
    assert (tmp_path / "fpl.md").exists()
