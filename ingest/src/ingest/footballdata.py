"""Load every Premier League match of both seasons from football-data.co.uk.

The statsbomb and understat loaders must run first: Arsenal's matches keep their
rows from those sources, and this loader links to them. Run from the repository root:
    uv run --env-file .env python -m ingest.footballdata
"""

import csv
import io
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx
import psycopg
from rapidfuzz import fuzz, process

from ingest import command, load, overrides

RAW_DIR = Path(__file__).resolve().parents[2] / "raw" / "football-data"
BASE_URL = "https://www.football-data.co.uk/mmz4281"
REQUEST_TIMEOUT_SECONDS = 30
# The 2025-26 file starts with a byte order mark. utf-8-sig reads both files.
ENCODING = "utf-8-sig"

SOURCE = "football-data"
TEAM = "Arsenal"
TEAMS_PER_SEASON = 20
# Each team plays each other team once at home and once away.
MATCHES_PER_VENUE = TEAMS_PER_SEASON - 1
MATCHES_PER_SEASON = TEAMS_PER_SEASON * MATCHES_PER_VENUE


@dataclass(frozen=True)
class SeasonFile:
    label: str
    # The folder of the season on the site: the last two digits of both years.
    code: str

    @property
    def file_name(self) -> str:
        return f"E0-{self.code}.csv"

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.code}/E0.csv"


SEASONS = (SeasonFile("2003-04", "0304"), SeasonFile("2025-26", "2526"))


# The points of the published final tables. They do not come from football-data,
# so that the check is against a second source. 2003-04: the build plan. 2025-26:
# premierleague.com, read by the project owner on 2026-10-23. Names as in teams.
EXPECTED_POINTS = {
    "2003-04": {"Arsenal": 90, "Chelsea": 79, "Manchester United": 75},
    "2025-26": {
        "Arsenal": 85,
        "Manchester City": 78,
        "Manchester United": 71,
        "Aston Villa": 65,
        "Liverpool": 60,
        "Bournemouth": 57,
        "Sunderland": 54,
        "Brighton": 53,
        "Brentford": 53,
        "Chelsea": 52,
        "Fulham": 52,
        "Newcastle United": 49,
        "Everton": 49,
        "Leeds United": 47,
        "Crystal Palace": 45,
        "Nottingham Forest": 44,
        "Tottenham Hotspur": 41,
        "West Ham": 39,
        "Burnley": 22,
        "Wolverhampton Wanderers": 20,
    },
}

# (home column, away column) of each team stat, in the order of TeamStats.
STAT_COLUMNS = (
    ("HS", "AS"),
    ("HST", "AST"),
    ("HC", "AC"),
    ("HF", "AF"),
    ("HY", "AY"),
    ("HR", "AR"),
)
COUNT_COLUMNS = ("FTHG", "FTAG", "HTHG", "HTAG", *(c for pair in STAT_COLUMNS for c in pair))
REQUIRED_COLUMNS = ("Date", "HomeTeam", "AwayTeam", "Referee", *COUNT_COLUMNS)


@dataclass(frozen=True)
class TeamStats:
    shots: int
    shots_on_target: int
    corners: int
    fouls: int
    yellow_cards: int
    red_cards: int


@dataclass(frozen=True)
class LeagueMatch:
    season: str
    match_date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    home_ht_goals: int
    away_ht_goals: int
    referee: str
    home: TeamStats
    away: TeamStats


def match_date(text: str) -> date:
    """Read a date of either file: 16/08/03 in 2003-04, 15/08/2025 in 2025-26."""
    year = "%Y" if len(text) == len("dd/mm/yyyy") else "%y"
    return datetime.strptime(text, f"%d/%m/{year}").date()


def parse_season(text: str, season: str, team_names: Mapping[str, str]) -> list[LeagueMatch]:
    """Turn one season file into matches. No I/O.

    team_names maps a source spelling to the name in teams, which the season loaders
    wrote first.

    Columns past the header (some 2003-04 rows have them) and every column that the
    plan does not name, such as the betting odds, are ignored.
    """
    reader = csv.DictReader(io.StringIO(text))
    if missing := [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]:
        raise ValueError(f"{season}: the file has no column {', '.join(missing)}")

    matches = []
    # Line 1 is the header, so the first match is on line 2.
    for line, row in enumerate(reader, start=2):
        for name in REQUIRED_COLUMNS:
            if not (row[name] or "").strip():
                raise ValueError(f"{season} line {line}: {name} is empty")
        for name in COUNT_COLUMNS:
            if not row[name].strip().isdigit():
                raise ValueError(f"{season} line {line}: {name} is {row[name]!r}, not a count")
        count = {name: int(row[name]) for name in COUNT_COLUMNS}
        matches.append(
            LeagueMatch(
                season=season,
                match_date=match_date(row["Date"].strip()),
                home_team=overrides.team_name(row["HomeTeam"].strip(), team_names),
                away_team=overrides.team_name(row["AwayTeam"].strip(), team_names),
                home_goals=count["FTHG"],
                away_goals=count["FTAG"],
                home_ht_goals=count["HTHG"],
                away_ht_goals=count["HTAG"],
                referee=row["Referee"].strip(),
                home=TeamStats(*(count[home] for home, _ in STAT_COLUMNS)),
                away=TeamStats(*(count[away] for _, away in STAT_COLUMNS)),
            )
        )
    check_schedule(matches, season)
    return matches


def check_schedule(matches: list[LeagueMatch], season: str) -> None:
    """Raise ValueError unless the matches are one full double round robin."""
    if len(matches) != MATCHES_PER_SEASON:
        raise ValueError(f"{season}: {len(matches)} matches, expected {MATCHES_PER_SEASON}")
    pairs = Counter((match.home_team, match.away_team) for match in matches)
    if repeated := [f"{home} v {away}" for (home, away), n in pairs.items() if n > 1]:
        raise ValueError(f"{season}: a fixture is in the file more than once: {repeated[0]}")
    home = Counter(match.home_team for match in matches)
    away = Counter(match.away_team for match in matches)
    teams = sorted(home.keys() | away.keys())
    if odd := [team for team in teams if (home[team], away[team]) != (MATCHES_PER_VENUE,) * 2]:
        raise ValueError(
            f"{season}: {odd[0]} has {home[odd[0]]} home and {away[odd[0]]} away matches,"
            f" expected {MATCHES_PER_VENUE} of each"
        )


def fetch_season(raw_dir: Path, season: SeasonFile, fetch: Callable[[SeasonFile], str]) -> str:
    """Return the text of a season file, downloading it only when it is not cached."""
    return command.cached_text(raw_dir / season.file_name, lambda: fetch(season), ENCODING)


def download(season: SeasonFile) -> str:
    try:
        response = httpx.get(season.url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as error:
        # Some networks cannot reach the site. A copy saved by hand works the same.
        raise command.FetchError(
            f"cannot download {season.url}: {type(error).__name__}."
            f" Save it by hand as {RAW_DIR / season.file_name}"
        ) from error
    return response.content.decode(ENCODING)


def build(
    raw_dir: Path = RAW_DIR, fetch: Callable[[SeasonFile], str] = download
) -> list[LeagueMatch]:
    """Read and parse both seasons, before any database connection opens."""
    team_names = overrides.read().teams
    return [
        match
        for season in SEASONS
        for match in parse_season(fetch_season(raw_dir, season, fetch), season.label, team_names)
    ]


def check_prerequisites(conn: psycopg.Connection, seasons: list[str]) -> dict[str, int]:
    """Return the database id of each season. Stop when a season loader did not run."""
    season_ids = dict(
        conn.execute("SELECT label, id FROM seasons WHERE label = ANY(%s)", (seasons,)).fetchall()
    )
    counts = dict(
        conn.execute(
            "SELECT s.label, count(*) FROM matches m"
            " JOIN seasons s ON s.id = m.season_id"
            " JOIN teams ht ON ht.id = m.home_team_id"
            " JOIN teams at ON at.id = m.away_team_id"
            " WHERE m.source <> %s AND %s IN (ht.name, at.name) AND s.label = ANY(%s)"
            " GROUP BY s.label",
            (SOURCE, TEAM, seasons),
        ).fetchall()
    )
    for season in seasons:
        # Run first, this loader would add Arsenal's matches, and the season loaders
        # would then add them a second time.
        if season not in season_ids or counts.get(season) != 2 * MATCHES_PER_VENUE:
            raise load.SanityError(
                f"{season} has {counts.get(season, 0)} {TEAM} matches from the season"
                f" loaders, expected {2 * MATCHES_PER_VENUE}. Load statsbomb and understat first"
            )
    return season_ids


def unknown_team(spelling: str, known: list[str]) -> str:
    """Name a spelling that is not in teams, with the closest club as a hint."""
    message = f"no team named {spelling} in teams; add the spelling to overrides.yaml"
    # Only a hint: an automatic fuzzy link could join Manchester City and United.
    if closest := process.extractOne(spelling, known, scorer=fuzz.WRatio):
        message += f" (closest team: {closest[0]})"
    return message


def load_matches(conn: psycopg.Connection, matches: list[LeagueMatch]) -> None:
    """Link Arsenal's matches, add the others, and write the team stats.

    The caller owns the transaction: nothing is committed here.
    """
    season_ids = check_prerequisites(conn, sorted({match.season for match in matches}))
    names = sorted({match.home_team for match in matches} | {match.away_team for match in matches})
    team_ids = dict(
        conn.execute("SELECT name, id FROM teams WHERE name = ANY(%s)", (names,)).fetchall()
    )
    # The season loaders wrote every club, because every club played Arsenal. An
    # unknown name is a spelling that overrides.yaml does not map yet.
    if missing := [name for name in names if name not in team_ids]:
        # Every club in teams: a new spelling means the file never names the canonical club.
        known = [name for (name,) in conn.execute("SELECT name FROM teams")]
        raise ValueError("; ".join(unknown_team(name, known) for name in missing))

    existing: dict[tuple[int, int, int], list[tuple]] = {}
    for row in conn.execute(
        "SELECT season_id, home_team_id, away_team_id, id, source, home_goals, away_goals"
        " FROM matches WHERE season_id = ANY(%s)",
        (list(season_ids.values()),),
    ):
        existing.setdefault(row[:3], []).append(row[3:])

    links = []
    new_rows = []
    for match in matches:
        key = (season_ids[match.season], team_ids[match.home_team], team_ids[match.away_team])
        others = [row for row in existing.get(key, []) if row[1] != SOURCE]
        name = f"{match.season} {match.home_team} v {match.away_team}"
        if TEAM in (match.home_team, match.away_team):
            if len(others) != 1:
                raise load.SanityError(f"{name} has {len(others)} rows to link to, expected 1")
            match_id, source, home_goals, away_goals = others[0]
            if (home_goals, away_goals) != (match.home_goals, match.away_goals):
                raise load.SanityError(
                    f"{name} is {home_goals}-{away_goals} in {source} and"
                    f" {match.home_goals}-{match.away_goals} in {SOURCE}"
                )
            links.append((match.home_ht_goals, match.away_ht_goals, match.referee, match_id))
        else:
            if others:
                raise load.SanityError(f"{name} already has a row from {others[0][1]}")
            new_rows.append((*key, match))

    with conn.cursor() as cur:
        # Only the new columns: the score and the date stay as the season loader wrote them.
        cur.executemany(
            "UPDATE matches SET home_ht_goals = %s, away_ht_goals = %s, referee = %s WHERE id = %s",
            links,
        )
        cur.executemany(
            "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id,"
            " home_goals, away_goals, home_ht_goals, away_ht_goals, referee, venue,"
            " source, source_match_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)"
            " ON CONFLICT (source, source_match_id) DO UPDATE SET"
            " season_id = EXCLUDED.season_id, match_date = EXCLUDED.match_date,"
            " home_team_id = EXCLUDED.home_team_id, away_team_id = EXCLUDED.away_team_id,"
            " home_goals = EXCLUDED.home_goals, away_goals = EXCLUDED.away_goals,"
            " home_ht_goals = EXCLUDED.home_ht_goals, away_ht_goals = EXCLUDED.away_ht_goals,"
            " referee = EXCLUDED.referee",
            [
                (
                    season_id,
                    match.match_date,
                    home_id,
                    away_id,
                    match.home_goals,
                    match.away_goals,
                    match.home_ht_goals,
                    match.away_ht_goals,
                    match.referee,
                    SOURCE,
                    f"{match.season}:{match.home_team}:{match.away_team}",
                )
                for season_id, home_id, away_id, match in new_rows
            ],
        )

    match_ids = {
        row[:3]: row[3]
        for row in conn.execute(
            "SELECT season_id, home_team_id, away_team_id, id FROM matches"
            " WHERE season_id = ANY(%s)",
            (list(season_ids.values()),),
        )
    }
    stats = []
    for match in matches:
        home_id, away_id = team_ids[match.home_team], team_ids[match.away_team]
        match_id = match_ids[(season_ids[match.season], home_id, away_id)]
        stats.append((match_id, home_id, match.home))
        stats.append((match_id, away_id, match.away))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO team_match_stats (match_id, team_id, shots, shots_on_target, corners,"
            " fouls, yellow_cards, red_cards, source)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (match_id, team_id) DO UPDATE SET"
            " shots = EXCLUDED.shots, shots_on_target = EXCLUDED.shots_on_target,"
            " corners = EXCLUDED.corners, fouls = EXCLUDED.fouls,"
            " yellow_cards = EXCLUDED.yellow_cards, red_cards = EXCLUDED.red_cards,"
            " source = EXCLUDED.source",
            [
                (
                    match_id,
                    team_id,
                    s.shots,
                    s.shots_on_target,
                    s.corners,
                    s.fouls,
                    s.yellow_cards,
                    s.red_cards,
                    SOURCE,
                )
                for match_id, team_id, s in stats
            ],
        )


def league_points(conn: psycopg.Connection, season: str) -> dict[str, tuple[int, int]]:
    """Return (matches played, points) of each team in the loaded season."""
    played: Counter = Counter()
    points: Counter = Counter()
    for home, away, home_goals, away_goals in conn.execute(
        "SELECT ht.name, at.name, m.home_goals, m.away_goals FROM matches m"
        " JOIN seasons s ON s.id = m.season_id"
        " JOIN teams ht ON ht.id = m.home_team_id"
        " JOIN teams at ON at.id = m.away_team_id"
        " WHERE s.label = %s",
        (season,),
    ):
        played.update((home, away))
        if home_goals == away_goals:
            points.update((home, away))
        else:
            points[home if home_goals > away_goals else away] += 3
    return {team: (played[team], points[team]) for team in played}


def check_league(conn: psycopg.Connection, season: str, expected: dict[str, int]) -> str:
    """Raise SanityError naming each difference from the published table.

    Return the summary line of the season.
    """
    table = league_points(conn, season)
    (linked,) = conn.execute(
        "SELECT count(*) FROM matches m"
        " JOIN seasons s ON s.id = m.season_id"
        " JOIN teams ht ON ht.id = m.home_team_id"
        " JOIN teams at ON at.id = m.away_team_id"
        " WHERE s.label = %s AND %s IN (ht.name, at.name) AND m.source <> %s"
        " AND m.referee IS NOT NULL",
        (season, TEAM, SOURCE),
    ).fetchone()
    total = sum(games for games, _ in table.values()) // 2
    problems = []
    if total != MATCHES_PER_SEASON:
        problems.append(f"{total} matches, expected {MATCHES_PER_SEASON}")
    problems += [
        f"{team} played {games}, expected {2 * MATCHES_PER_VENUE}"
        for team, (games, _) in sorted(table.items())
        if games != 2 * MATCHES_PER_VENUE
    ]
    if linked != 2 * MATCHES_PER_VENUE:
        problems.append(f"{linked} {TEAM} matches linked, expected {2 * MATCHES_PER_VENUE}")
    problems += [
        f"{team} has {table.get(team, (0, 0))[1]} points, expected {points}"
        for team, points in expected.items()
        if table.get(team, (0, 0))[1] != points
    ]
    if problems:
        raise load.SanityError(f"{season}: " + "; ".join(problems))
    shown = ", ".join(f"{team} {points}" for team, points in list(expected.items())[:3])
    return (
        f"{season}: {total} matches, {linked} {TEAM} matches linked,"
        f" {len(expected)} published points equal ({shown}"
        f"{', ...' if len(expected) > 3 else ''})"
    )


def load_league(url: str, matches: list[LeagueMatch]) -> list[str]:
    """Load and check both seasons in one transaction. Return the lines to print."""
    # The connection block commits on a clean exit and rolls back on an error, so a
    # load that fails the check never reaches the database.
    with psycopg.connect(url, connect_timeout=command.CONNECT_TIMEOUT_SECONDS) as conn:
        load_matches(conn, matches)
        lines = [
            f"{table}: {conn.execute(f'SELECT count(*) FROM {table}').fetchone()[0]}"
            # The names come from this tuple, never from input.
            for table in ("matches", "team_match_stats")
        ]
        lines += [
            check_league(conn, season.label, EXPECTED_POINTS[season.label]) for season in SEASONS
        ]
    return lines


def main() -> int:
    return command.execute(lambda url: load_league(url, build()))


if __name__ == "__main__":
    sys.exit(main())
