import csv
import io
from dataclasses import replace
from datetime import date

import httpx
import psycopg
import pytest

from ingest import command, footballdata, load, overrides
from ingest.footballdata import LeagueMatch, SeasonFile, TeamStats

# Three spellings that the map changes, one that it keeps, and sixteen made up.
SPELLINGS = [
    "Arsenal",
    "Man United",
    "Nott'm Forest",
    "Chelsea",
    *(f"Club {n:02}" for n in range(16)),
]
TEAMS = {"Man United": "Manchester United", "Nott'm Forest": "Nottingham Forest"}
NAMES = [overrides.team_name(spelling, TEAMS) for spelling in SPELLINGS]
HEADER = ["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR"]
HEADER += ["Referee", "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"]
HEADER += ["B365H"]


def score(home: int, away: int) -> tuple[int, int]:
    return (home + 2 * away) % 4, (home * away) % 3


def fixtures() -> list[tuple[int, int]]:
    """Each pair of clubs, home and away: a full season of 380 matches."""
    return [(h, a) for h in range(len(SPELLINGS)) for a in range(len(SPELLINGS)) if h != a]


def league_csv(dates: str = "16/08/03", rows=None, extra=None) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(HEADER)
    for home, away in rows if rows is not None else fixtures():
        hg, ag = score(home, away)
        line = ["E0", dates, SPELLINGS[home], SPELLINGS[away], hg, ag, "H", 0, 0, "D", "M Dean"]
        line += [12, 7, 5, 3, 10, 11, 6, 2, 1, 2, 0, 0, 1.5]
        writer.writerow(line + (extra or []))
    return out.getvalue()


def test_a_season_file_becomes_380_matches_with_canonical_names():
    matches = footballdata.parse_season(league_csv(), "2003-04", TEAMS)

    assert len(matches) == 380
    first = matches[0]
    assert first == LeagueMatch(
        season="2003-04",
        match_date=date(2003, 8, 16),
        home_team="Arsenal",
        away_team="Manchester United",
        home_goals=2,
        away_goals=0,
        home_ht_goals=0,
        away_ht_goals=0,
        referee="M Dean",
        home=TeamStats(12, 5, 6, 10, 1, 0),
        away=TeamStats(7, 3, 2, 11, 2, 0),
    )
    assert {match.home_team for match in matches} == set(NAMES)


@pytest.mark.parametrize(
    ("text", "expected"), [("16/08/03", date(2003, 8, 16)), ("24/05/2026", date(2026, 5, 24))]
)
def test_both_date_formats_are_read(text, expected):
    assert footballdata.match_date(text) == expected


def test_cells_past_the_header_are_ignored():
    matches = footballdata.parse_season(league_csv(extra=["", "9.5", "x"]), "2003-04", TEAMS)

    assert len(matches) == 380


def test_the_byte_order_mark_is_not_part_of_the_first_column(tmp_path):
    path = tmp_path / "E0-2526.csv"
    path.write_text(league_csv(dates="15/08/2025"), encoding="utf-8-sig")

    text = footballdata.fetch_season(tmp_path, SeasonFile("2025-26", "2526"), pytest.fail)

    assert footballdata.parse_season(text, "2025-26", TEAMS)[0].match_date == date(2025, 8, 15)


def replace_cell(text: str, line: int, column: str, value: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    rows[line - 1][HEADER.index(column)] = value
    out = io.StringIO()
    csv.writer(out, lineterminator="\r\n").writerows(rows)
    return out.getvalue()


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("HS", "", "2003-04 line 3: HS is empty"),
        ("Referee", " ", "2003-04 line 3: Referee is empty"),
        ("FTHG", "two", "2003-04 line 3: FTHG is 'two', not a count"),
        ("HY", "-1", "2003-04 line 3: HY is '-1', not a count"),
    ],
)
def test_a_cell_that_is_not_a_count_names_its_line_and_column(column, value, reason):
    with pytest.raises(ValueError) as error:
        footballdata.parse_season(replace_cell(league_csv(), 3, column, value), "2003-04", TEAMS)

    assert str(error.value) == reason


def test_a_missing_column_is_named():
    text = league_csv().replace(",Referee,", ",Ref,", 1)

    with pytest.raises(ValueError, match="the file has no column Referee"):
        footballdata.parse_season(text, "2003-04", TEAMS)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (league_csv(rows=fixtures()[:-1]), "379 matches, expected 380"),
        (
            league_csv(rows=fixtures()[:-1] + [fixtures()[0]]),
            "more than once: Arsenal v Manchester United",
        ),
        # A 21st club in the last match: the club it replaces misses an away match.
        (
            replace_cell(league_csv(), 381, "AwayTeam", "Club 99"),
            "expected 19 of each",
        ),
    ],
)
def test_a_season_that_is_not_a_full_double_round_robin_is_rejected(text, reason):
    with pytest.raises(ValueError, match=reason):
        footballdata.parse_season(text, "2003-04", TEAMS)


def test_a_cached_file_is_read_without_a_download(tmp_path):
    (tmp_path / "E0-0304.csv").write_text("cached", encoding="utf-8")

    assert footballdata.fetch_season(tmp_path, footballdata.SEASONS[0], pytest.fail) == "cached"


def test_a_download_is_written_through_a_rename(tmp_path):
    text = footballdata.fetch_season(tmp_path, footballdata.SEASONS[1], lambda season: "a,b\r\n")

    assert text == "a,b\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["E0-2526.csv"]
    # The bytes on disk are the download's, with no doubled line end on Windows.
    assert (tmp_path / "E0-2526.csv").read_bytes() == b"\xef\xbb\xbfa,b\r\n"


def test_a_failed_download_says_where_to_save_the_file(monkeypatch):
    def refuse(url, timeout):
        raise httpx.ConnectTimeout("no route")

    monkeypatch.setattr(footballdata.httpx, "get", refuse)

    with pytest.raises(command.FetchError) as error:
        footballdata.download(footballdata.SEASONS[0])

    assert "mmz4281/0304/E0.csv" in str(error.value)
    assert "Save it by hand as" in str(error.value)
    assert str(error.value).endswith("E0-0304.csv")


# The database half: the season loaders' rows first, then this loader.


def seed(conn: psycopg.Connection, *, arsenal_matches: int = 38, wrong_score: bool = False) -> None:
    """2003-04 as the StatsBomb loader leaves it: every club, and Arsenal's matches."""
    conn.execute("INSERT INTO seasons VALUES (2003, '2003-04', 'EVENT')")
    ids = {
        name: conn.execute("INSERT INTO teams (name) VALUES (%s) RETURNING id", (name,)).fetchone()[
            0
        ]
        for name in NAMES
    }
    arsenal = [(h, a) for h, a in fixtures() if 0 in (h, a)][:arsenal_matches]
    for number, (home, away) in enumerate(arsenal):
        hg, ag = score(home, away)
        conn.execute(
            "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id,"
            " home_goals, away_goals, venue, source, source_match_id)"
            " VALUES (2003, '2003-08-16', %s, %s, %s, %s, 'Highbury', 'statsbomb', %s)",
            (
                ids[NAMES[home]],
                ids[NAMES[away]],
                hg + (wrong_score and number == 5),
                ag,
                f"sb{number}",
            ),
        )


def parsed() -> list[LeagueMatch]:
    return footballdata.parse_season(league_csv(), "2003-04", TEAMS)


def snapshot(conn) -> tuple:
    matches = conn.execute(
        "SELECT id, source, source_match_id, home_goals, away_goals, home_ht_goals,"
        " away_ht_goals, referee, venue FROM matches ORDER BY id"
    ).fetchall()
    stats = conn.execute("SELECT * FROM team_match_stats ORDER BY match_id, team_id").fetchall()
    return matches, stats


def test_arsenal_matches_link_to_their_rows_and_the_others_are_added(ingest):
    seed(ingest)

    footballdata.load_matches(ingest, parsed())

    rows = ingest.execute(
        "SELECT source, count(*), count(referee), count(venue) FROM matches GROUP BY source"
        " ORDER BY source"
    ).fetchall()
    # 38 Arsenal rows keep their source and venue and gain a referee. 342 are new.
    assert rows == [("football-data", 342, 342, 0), ("statsbomb", 38, 38, 38)]
    assert ingest.execute("SELECT count(*) FROM team_match_stats").fetchone() == (760,)
    assert ingest.execute(
        "SELECT source_match_id FROM matches WHERE source = 'football-data' ORDER BY id LIMIT 1"
    ).fetchone() == ("2003-04:Manchester United:Nottingham Forest",)


def test_a_second_run_changes_nothing(ingest):
    seed(ingest)
    footballdata.load_matches(ingest, parsed())
    before = snapshot(ingest)

    footballdata.load_matches(ingest, parsed())

    assert snapshot(ingest) == before


def test_a_season_loader_run_afterwards_keeps_the_links_and_the_stats(ingest):
    seed(ingest)
    footballdata.load_matches(ingest, parsed())
    before = snapshot(ingest)
    statsbomb_rows = ingest.execute(
        "SELECT source_match_id, match_date, ht.name, at.name, home_goals, away_goals, venue"
        " FROM matches m JOIN teams ht ON ht.id = m.home_team_id"
        " JOIN teams at ON at.id = m.away_team_id WHERE source = 'statsbomb'"
    ).fetchall()

    # The upsert of the season loaders, with the same rows as before.
    load.load(
        ingest,
        load.SeasonRows(
            season_id=2003,
            season_label="2003-04",
            data_level="EVENT",
            source="statsbomb",
            teams=NAMES,
            players=[],
            matches=[load.MatchRow(*row) for row in statsbomb_rows],
            shots=[],
            events=[],
            stats=[],
        ),
    )

    assert snapshot(ingest) == before


def test_a_score_that_differs_from_the_season_loader_stops_the_load(ingest):
    seed(ingest, wrong_score=True)

    with pytest.raises(
        load.SanityError, match="Arsenal v Club 02 is 1-0 in statsbomb and 0-0 in football-data"
    ):
        footballdata.load_matches(ingest, parsed())


def test_the_load_stops_when_the_season_loaders_did_not_run(ingest):
    seed(ingest, arsenal_matches=0)

    with pytest.raises(load.SanityError) as error:
        footballdata.load_matches(ingest, parsed())

    assert str(error.value) == (
        "2003-04 has 0 Arsenal matches from the season loaders, expected 38."
        " Load statsbomb and understat first"
    )


def test_a_club_that_is_not_in_teams_is_named(ingest):
    seed(ingest)
    matches = [
        match if match.away_team != "Club 15" else replace(match, away_team="Club 99")
        for match in parsed()
    ]

    with pytest.raises(ValueError, match="no team named Club 99 in teams") as error:
        footballdata.load_matches(ingest, matches)

    assert "add the spelling to overrides.yaml" in str(error.value)


def test_an_unknown_spelling_names_the_closest_team_as_a_hint(ingest):
    seed(ingest)

    def renamed(team: str) -> str:
        return "Man Utd" if team == "Manchester United" else team

    # A new spelling replaces the club in every row, so the file never names the
    # canonical club: the hint must come from teams, not from the file.
    matches = [
        replace(match, home_team=renamed(match.home_team), away_team=renamed(match.away_team))
        for match in parsed()
    ]

    with pytest.raises(
        ValueError, match=r"no team named Man Utd .*\(closest team: Manchester United\)"
    ):
        footballdata.load_matches(ingest, matches)

    # The hint is never applied: no row was written.
    assert ingest.execute("SELECT count(*) FROM team_match_stats").fetchone() == (0,)


def test_a_match_without_arsenal_cannot_take_the_row_of_another_source(ingest):
    seed(ingest)
    ids = dict(ingest.execute("SELECT name, id FROM teams").fetchall())
    ingest.execute(
        "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id, home_goals,"
        " away_goals, source, source_match_id)"
        " VALUES (2003, '2003-08-16', %s, %s, 0, 0, 'understat', 'u1')",
        (ids["Chelsea"], ids["Club 00"]),
    )

    with pytest.raises(
        load.SanityError, match="Chelsea v Club 00 already has a row from understat"
    ):
        footballdata.load_matches(ingest, parsed())


def test_the_league_check_passes_on_the_published_points(ingest):
    seed(ingest)
    footballdata.load_matches(ingest, parsed())
    table = footballdata.league_points(ingest, "2003-04")

    line = footballdata.check_league(
        ingest, "2003-04", {"Arsenal": table["Arsenal"][1], "Chelsea": table["Chelsea"][1]}
    )

    assert line.startswith("2003-04: 380 matches, 38 Arsenal matches linked, 2 published points")
    assert all(games == 38 for games, _ in table.values())


def test_the_league_check_names_each_difference(ingest):
    seed(ingest)
    footballdata.load_matches(ingest, parsed())
    arsenal = footballdata.league_points(ingest, "2003-04")["Arsenal"][1]

    with pytest.raises(load.SanityError) as error:
        footballdata.check_league(ingest, "2003-04", {"Arsenal": arsenal + 1, "Chelsea": 999})

    assert f"Arsenal has {arsenal} points, expected {arsenal + 1}" in str(error.value)
    assert "expected 999" in str(error.value)


def test_the_published_tables_list_every_2025_26_club_once():
    points = footballdata.EXPECTED_POINTS["2025-26"]

    assert len(points) == 20
    assert points["Arsenal"] == 85
    assert footballdata.EXPECTED_POINTS["2003-04"] == {
        "Arsenal": 90,
        "Chelsea": 79,
        "Manchester United": 75,
    }
