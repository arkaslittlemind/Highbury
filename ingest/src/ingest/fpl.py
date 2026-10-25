"""Load the 2025-26 FPL player data of each match from the vaastav archive.

The live FPL API serves only the current season, so 2025-26 comes from
github.com/vaastav/Fantasy-Premier-League. The understat and footballdata loaders
must run first: every FPL row links to one of the 380 league matches, and its
player links to the Understat player where there is one. Run from the repository root:
    uv run --env-file .env python -m ingest.fpl
"""

import csv
import io
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
import psycopg

from ingest import command, footballdata, load, overrides, resolve, understat

RAW_DIR = Path(__file__).resolve().parents[2] / "raw" / "fpl"
BASE_URL = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26"
REQUEST_TIMEOUT_SECONDS = 30

SOURCE = "fpl"
SEASON = "2025-26"
GAMEWEEKS = 38

# Goals that the two sources give to different players, as (canonical player: FPL goals
# minus Understat goals in Arsenal's matches). Each one was checked in both raw files.
# Leeds 0-4 Arsenal, 2026-01-31: Understat (match 29015) has the 37th-minute goal as an
# own goal by Karl Darlow; FPL gives it to Madueke and has no own goal in the match.
GOAL_DIFFERENCES = {"Noni Madueke": 1}

# The cache file name of each raw file, and its path in the archive.
GW_FILE = "merged_gw.csv"
FIXTURES_FILE = "fixtures.csv"
TEAMS_FILE = "teams.csv"
ARCHIVE_PATHS = {
    GW_FILE: "gws/merged_gw.csv",
    FIXTURES_FILE: "fixtures.csv",
    TEAMS_FILE: "teams.csv",
}

# (column, field of FplRow) of each count. BPS and points can be negative.
COUNTS = (
    ("minutes", "minutes"),
    ("goals_scored", "goals"),
    ("assists", "assists"),
    ("saves", "saves"),
    ("bonus", "bonus"),
    ("yellow_cards", "yellow_cards"),
    ("red_cards", "red_cards"),
    ("defensive_contribution", "defensive_contribution"),
)
SIGNED = (("bps", "bps"), ("total_points", "points"))
GW_COLUMNS = (
    "element",
    "name",
    "team",
    "fixture",
    "clean_sheets",
    "value",
    *(column for column, _ in COUNTS + SIGNED),
)
FIXTURE_COLUMNS = ("id", "event", "team_h", "team_a")
TEAM_COLUMNS = ("id", "name")


@dataclass(frozen=True)
class FplRow:
    # The FPL element id of the player.
    player: str
    team: str
    home_team: str
    away_team: str
    gameweek: int
    minutes: int
    goals: int
    assists: int
    clean_sheet: bool
    saves: int
    bonus: int
    bps: int
    yellow_cards: int
    red_cards: int
    defensive_contribution: int
    points: int
    # Millions of pounds.
    price: Decimal


@dataclass(frozen=True)
class FplSeason:
    players: list[load.PlayerRow]
    rows: list[FplRow]


def read_csv(text: str, file: str, columns: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    """Return each row with its line number. Raise ValueError when a column is absent."""
    reader = csv.DictReader(io.StringIO(text))
    if missing := [name for name in columns if name not in (reader.fieldnames or [])]:
        raise ValueError(f"{file}: the file has no column {', '.join(missing)}")
    # Line 1 is the header, so the first row is on line 2.
    return list(enumerate(reader, start=2))


def integer(row: dict[str, str], column: str, where: str, signed: bool = False) -> int:
    text = (row[column] or "").strip()
    digits = text[1:] if signed and text.startswith("-") else text
    if not digits.isdigit():
        kind = "an integer" if signed else "a count"
        raise ValueError(f"{where}: {column} is {row[column]!r}, not {kind}")
    return int(text)


def parse(
    gw_text: str, fixtures_text: str, teams_text: str, team_names: Mapping[str, str]
) -> FplSeason:
    """Turn the three raw files into rows. No I/O.

    team_names maps a source spelling to the name in teams. Rows with no minutes are
    dropped: a player who did not play has no FPL numbers.
    """
    team_by_id = {}
    for line, row in read_csv(teams_text, TEAMS_FILE, TEAM_COLUMNS):
        name = (row["name"] or "").strip()
        if not name:
            raise ValueError(f"{TEAMS_FILE} line {line}: name is empty")
        team_by_id[row["id"].strip()] = overrides.team_name(name, team_names)

    # fixture id to (home team, away team, gameweek or None).
    fixtures: dict[str, tuple[str, str, int | None]] = {}
    for line, row in read_csv(fixtures_text, FIXTURES_FILE, FIXTURE_COLUMNS):
        where = f"{FIXTURES_FILE} line {line}"
        sides = []
        for column in ("team_h", "team_a"):
            if (team_id := row[column].strip()) not in team_by_id:
                raise ValueError(f"{where}: {column} {team_id!r} is not in {TEAMS_FILE}")
            sides.append(team_by_id[team_id])
        # A postponed match with no new date has no gameweek. Only a row with minutes needs one.
        event = integer(row, "event", where) if row["event"].strip() else None
        fixtures[row["id"].strip()] = (sides[0], sides[1], event)

    seen: dict[tuple[str, str], dict[str, str]] = {}
    names: dict[str, str] = {}
    rows = []
    for line, row in read_csv(gw_text, GW_FILE, GW_COLUMNS):
        where = f"{GW_FILE} line {line}"
        player, fixture = row["element"].strip(), row["fixture"].strip()
        if (earlier := seen.setdefault((player, fixture), row)) is not row:
            # The archive repeats a few rows exactly. A repeat that differs is two answers.
            if earlier != row:
                raise ValueError(
                    f"{where}: player {player} has a second, different row for fixture {fixture}"
                )
            continue
        if integer(row, "minutes", where) == 0:
            continue

        if fixture not in fixtures:
            raise ValueError(f"{where}: fixture {fixture!r} is not in {FIXTURES_FILE}")
        home, away, gameweek = fixtures[fixture]
        if gameweek is None or not 1 <= gameweek <= GAMEWEEKS:
            raise ValueError(f"{where}: fixture {fixture} has no gameweek from 1 to {GAMEWEEKS}")
        team = overrides.team_name((row["team"] or "").strip(), team_names)
        if team not in (home, away):
            raise ValueError(f"{where}: {team!r} is not a side of fixture {fixture}")
        name = (row["name"] or "").strip()
        if not name:
            raise ValueError(f"{where}: name is empty")
        # One element is one player. Two names would give one record two identities.
        if names.setdefault(player, name) != name:
            raise ValueError(f"{where}: player {player} is {name!r} and {names[player]!r}")
        clean_sheets = integer(row, "clean_sheets", where)
        if clean_sheets > 1:
            raise ValueError(f"{where}: clean_sheets is {clean_sheets}, not 0 or 1")
        value = integer(row, "value", where)
        if value == 0:
            raise ValueError(f"{where}: value is 0, not a price")

        rows.append(
            FplRow(
                player=player,
                team=team,
                home_team=home,
                away_team=away,
                gameweek=gameweek,
                clean_sheet=clean_sheets == 1,
                # value is in tenths of a million. Decimal keeps 5.5 exact.
                price=Decimal(value) / 10,
                **{field: integer(row, column, where) for column, field in COUNTS},
                **{field: integer(row, column, where, signed=True) for column, field in SIGNED},
            )
        )

    players = [load.PlayerRow(player, name, name, None) for player, name in names.items()]
    return FplSeason(players, rows)


def fetch_file(raw_dir: Path, file: str, fetch: Callable[[str], str]) -> str:
    """Return the text of a raw file, downloading it only when it is not cached."""
    return command.cached_text(raw_dir / file, lambda: fetch(file))


def download(file: str) -> str:
    url = f"{BASE_URL}/{ARCHIVE_PATHS[file]}"
    try:
        response = httpx.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise command.FetchError(
            f"cannot download {url}: {type(error).__name__}. Save it by hand as {RAW_DIR / file}"
        ) from error
    return response.content.decode("utf-8")


def build(raw_dir: Path = RAW_DIR, fetch: Callable[[str], str] = download) -> FplSeason:
    """Read and parse the season, before any database connection opens."""
    team_names = overrides.read().teams
    return parse(*(fetch_file(raw_dir, file, fetch) for file in ARCHIVE_PATHS), team_names)


class SourceMismatch(load.SanityError):
    """FPL and Understat disagree in Arsenal's matches. Carries the review rows, for the report."""

    def __init__(self, message: str, rows: load.SeasonRows, review: list[resolve.ReviewRow]):
        super().__init__(message)
        self.rows = rows
        self.review = review


def check_prerequisites(conn: psycopg.Connection) -> tuple[int, str]:
    """Return the id and data level of the season. Stop when a loader it needs did not run."""
    found = conn.execute(
        "SELECT id, data_level FROM seasons WHERE label = %s", (SEASON,)
    ).fetchone()
    total, covered = (
        conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE source = %s) FROM matches"
            " WHERE season_id = %s",
            (understat.SOURCE, found[0]),
        ).fetchone()
        if found
        else (0, 0)
    )
    # Without Understat there is nothing to check the goals against; without
    # football-data most FPL rows have no match.
    if (total, covered) != (footballdata.MATCHES_PER_SEASON, 2 * footballdata.MATCHES_PER_VENUE):
        raise load.SanityError(
            f"{SEASON} has {total} league matches, {covered} of them from Understat, expected"
            f" {footballdata.MATCHES_PER_SEASON} and {2 * footballdata.MATCHES_PER_VENUE}."
            " Load understat and footballdata first"
        )
    return found


def match_key(row: FplRow) -> str:
    return f"{row.home_team}:{row.away_team}"


def check_pairs(conn: psycopg.Connection, season_id: int) -> list[str]:
    """Name each player row of an Understat match that the other source does not have.

    Understat has both teams of Arsenal's matches, so in those matches every FPL row
    has an Understat row of the same player, and the reverse. A row with no partner is
    a missed link, which the goals check cannot see when the player did not score.
    """
    unpaired = conn.execute(
        "WITH covered AS (SELECT id FROM matches WHERE season_id = %s AND source = %s)"
        " SELECT 'no Understat row', player_id, match_id FROM fpl_player_match f"
        "  WHERE match_id IN (SELECT id FROM covered) AND NOT EXISTS (SELECT 1"
        "  FROM player_match_stats s WHERE s.player_id = f.player_id AND s.match_id = f.match_id)"
        " UNION ALL"
        " SELECT 'no FPL row', player_id, match_id FROM player_match_stats s"
        # Understat lists an unused substitute with 0 minutes; FPL has no row for him.
        "  WHERE match_id IN (SELECT id FROM covered) AND minutes > 0 AND NOT EXISTS (SELECT 1"
        "  FROM fpl_player_match f WHERE f.player_id = s.player_id AND f.match_id = s.match_id)",
        (season_id, understat.SOURCE),
    ).fetchall()
    names = dict(
        conn.execute(
            "SELECT id, name FROM players WHERE id = ANY(%s)", ([p for _, p, _ in unpaired],)
        ).fetchall()
    )
    dates = dict(
        conn.execute(
            "SELECT id, match_date FROM matches WHERE id = ANY(%s)", ([m for _, _, m in unpaired],)
        ).fetchall()
    )
    return sorted(
        f"{names[player]} on {dates[match].isoformat()}: {problem}"
        for problem, player, match in unpaired
    )


def check_goals(conn: psycopg.Connection, season_id: int) -> tuple[int, int, list[str]]:
    """Compare each player's goals in the Understat matches.

    Return the number of players compared, how many of them have a known difference,
    and the differences that are not known.

    Understat has only Arsenal's matches, so these are the matches both sources cover.
    A missed link shows here too: one player with Understat goals and no FPL goals.
    A difference in GOAL_DIFFERENCES is expected; any other one is not.
    """
    rows = conn.execute(
        "WITH covered AS (SELECT id FROM matches WHERE season_id = %s AND source = %s),"
        " u AS (SELECT player_id, sum(goals) AS goals FROM player_match_stats"
        "  WHERE match_id IN (SELECT id FROM covered) GROUP BY player_id),"
        " f AS (SELECT player_id, sum(goals) AS goals FROM fpl_player_match"
        "  WHERE match_id IN (SELECT id FROM covered) GROUP BY player_id)"
        " SELECT p.name, coalesce(u.goals, 0), coalesce(f.goals, 0)"
        " FROM u FULL JOIN f USING (player_id) JOIN players p ON p.id = player_id"
        " ORDER BY p.name, p.id",
        (season_id, understat.SOURCE),
    ).fetchall()
    known = sum(name in GOAL_DIFFERENCES for name, _, _ in rows)
    return (
        len(rows),
        known,
        [
            f"{name}: Understat {expected}, FPL {found}"
            for name, expected, found in rows
            if expected + GOAL_DIFFERENCES.get(name, 0) != found
        ],
    )


def load_fpl(
    conn: psycopg.Connection,
    season: FplSeason,
    player_overrides: Mapping[tuple[str, str], overrides.PlayerOverride],
) -> tuple[list[str], load.SeasonRows, list[resolve.ReviewRow]]:
    """Link, resolve, write, and check the season. Return the lines, the rows, and the review.

    The caller owns the transaction: nothing is committed here.
    """
    season_id, data_level = check_prerequisites(conn)
    names = sorted(
        {row.team for row in season.rows}
        | {row.home_team for row in season.rows}
        | {row.away_team for row in season.rows}
    )
    team_ids = dict(
        conn.execute("SELECT name, id FROM teams WHERE name = ANY(%s)", (names,)).fetchall()
    )
    if missing := [name for name in names if name not in team_ids]:
        known = [name for (name,) in conn.execute("SELECT name FROM teams")]
        raise ValueError("; ".join(footballdata.unknown_team(name, known) for name in missing))

    candidates: dict[tuple[int, int], list[int]] = {}
    for home_id, away_id, match_id in conn.execute(
        "SELECT home_team_id, away_team_id, id FROM matches WHERE season_id = %s", (season_id,)
    ):
        candidates.setdefault((home_id, away_id), []).append(match_id)
    match_ids = {}
    for row in season.rows:
        key = (team_ids[row.home_team], team_ids[row.away_team])
        if len(found := candidates.get(key, [])) != 1:
            raise load.SanityError(
                f"{SEASON} {row.home_team} v {row.away_team} has {len(found)} matches to link"
                " to, expected 1"
            )
        match_ids[match_key(row)] = found[0]

    # load_players reads only the source, the season, the players, and the player and
    # team of each stat. load.load is not called: it would write player_match_stats.
    rows = load.SeasonRows(
        season_id=season_id,
        season_label=SEASON,
        data_level=data_level,
        source=SOURCE,
        teams=names,
        players=season.players,
        matches=[],
        shots=[],
        events=[],
        stats=[
            load.StatRow(
                row.player,
                match_key(row),
                row.team,
                row.minutes,
                row.goals,
                row.assists,
                None,
                None,
            )
            for row in season.rows
        ],
    )
    player_ids, review = load.load_players(conn, rows, team_ids, player_overrides)

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO fpl_player_match (player_id, match_id, team_id, gameweek, minutes,"
            " goals, assists, clean_sheet, saves, bonus, bps, yellow_cards, red_cards,"
            " defensive_contribution, points, price)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (player_id, match_id) DO UPDATE SET"
            " team_id = EXCLUDED.team_id, gameweek = EXCLUDED.gameweek,"
            " minutes = EXCLUDED.minutes, goals = EXCLUDED.goals, assists = EXCLUDED.assists,"
            " clean_sheet = EXCLUDED.clean_sheet, saves = EXCLUDED.saves,"
            " bonus = EXCLUDED.bonus, bps = EXCLUDED.bps, yellow_cards = EXCLUDED.yellow_cards,"
            " red_cards = EXCLUDED.red_cards,"
            " defensive_contribution = EXCLUDED.defensive_contribution,"
            " points = EXCLUDED.points, price = EXCLUDED.price",
            [
                (
                    player_ids[row.player],
                    match_ids[match_key(row)],
                    team_ids[row.team],
                    row.gameweek,
                    row.minutes,
                    row.goals,
                    row.assists,
                    row.clean_sheet,
                    row.saves,
                    row.bonus,
                    row.bps,
                    row.yellow_cards,
                    row.red_cards,
                    row.defensive_contribution,
                    row.points,
                    row.price,
                )
                for row in season.rows
            ],
        )

    problems = []
    if unpaired := check_pairs(conn, season_id):
        problems.append(
            f"{len(unpaired)} player rows of Arsenal's matches have no partner in the other"
            " source: " + "; ".join(unpaired)
        )
    compared, known, mismatches = check_goals(conn, season_id)
    if mismatches:
        problems.append(
            f"FPL goals differ from Understat's for {len(mismatches)} players: "
            + "; ".join(mismatches)
        )
    if problems:
        raise SourceMismatch(". ".join(problems), rows, review)

    counts = load.table_counts(conn)
    (fpl_rows,) = conn.execute("SELECT count(*) FROM fpl_player_match").fetchone()
    aliases, joined = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM player_aliases o"
        "  WHERE o.player_id = a.player_id AND o.source <> ALL(%s)))"
        " FROM player_aliases a WHERE a.source = %s",
        ([SOURCE, load.MANUAL_SOURCE], SOURCE),
    ).fetchone()
    lines = [
        f"players: {counts['players']}",
        f"player_aliases: {counts['player_aliases']}",
        f"fpl_player_match: {fpl_rows}",
        f"FPL players with minutes: {len(season.players)}, {aliases} with an fpl alias,"
        f" {joined} linked to a player of another source",
        f"source check: every player row of the {2 * footballdata.MATCHES_PER_VENUE}"
        f" Understat matches is in both sources; {compared} players have the same goals"
        + (f", {known} of them with a known difference" if known else ""),
    ]
    return lines, rows, review


def load_season(
    url: str,
    season: FplSeason,
    player_overrides: Mapping[tuple[str, str], overrides.PlayerOverride],
) -> tuple[list[str], load.SeasonRows, list[resolve.ReviewRow]]:
    """Load and check the season in one transaction."""
    # The connection block commits on a clean exit and rolls back on an error, so a
    # season that fails the check never reaches the database.
    with psycopg.connect(url, connect_timeout=command.CONNECT_TIMEOUT_SECONDS) as conn:
        return load_fpl(conn, season, player_overrides)


def run(
    build: Callable[[], FplSeason] = build,
    env: Mapping[str, str] = os.environ,
    review_dir: Path = resolve.REVIEW_DIR,
) -> int:
    """Run the command and return its exit code."""
    path = review_dir / f"{SOURCE}.md"

    def task(url: str) -> list[str]:
        season = build()
        try:
            lines, rows, review = load_season(url, season, overrides.read().players)
        except SourceMismatch as error:
            # Nothing was committed, but the report shows the name links behind the
            # mismatch, which is what the user needs to write the overrides.
            raise load.SanityError(
                f"{error}; {command.review_line(path, error.rows, error.review)}"
            ) from error
        return [*lines, command.review_line(path, rows, review)]

    return command.execute(task, env)


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
