"""Write one season's rows to the database as the ingest role."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import psycopg

from ingest import resolve
from ingest.migrate import SettingsError
from ingest.overrides import PlayerOverride

INGEST_URL_VAR = "INGEST_DATABASE_URL"
# The source of the fan nicknames, which ingest.curated loads.
MANUAL_SOURCE = "manual"

# The tables a season load writes, in dependency order.
SEASON_TABLES = (
    "seasons",
    "teams",
    "players",
    "player_aliases",
    "matches",
    "shots",
    "events",
    "player_match_stats",
)


class CoordinateError(ValueError):
    """A source record has a location outside the 120 x 80 pitch."""


# Rows name their match, player, and team by the source's own ids and names. The
# loader swaps them for database ids, so a source module needs no database access.


@dataclass(frozen=True)
class PlayerRow:
    source_id: str
    name: str
    source_name: str
    position: str | None


@dataclass(frozen=True)
class MatchRow:
    source_id: str
    match_date: date
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    venue: str | None


@dataclass(frozen=True)
class ShotRow:
    source_id: str
    match: str
    player: str
    team: str
    minute: int
    x: float
    y: float
    xg: float
    outcome: str
    body_part: str | None
    situation: str | None
    # Last, with a default, because tests build this row by position.
    aerial_won: bool = False


@dataclass(frozen=True)
class EventRow:
    source_id: str
    match: str
    player: str | None
    team: str
    type: str
    minute: int
    second: int
    x: float | None
    y: float | None
    end_x: float | None
    end_y: float | None
    outcome: str | None
    under_pressure: bool
    possession: int | None
    recipient: str | None
    # Last, with defaults, because tests build this row by position.
    period: int | None = None
    # The details of a pass, a duel, or an aerial win. None or False on other types.
    pass_length: float | None = None
    pass_type: str | None = None
    shot_assist: bool = False
    goal_assist: bool = False
    aerial_won: bool = False
    duel_type: str | None = None


@dataclass(frozen=True)
class StatRow:
    player: str
    match: str
    team: str
    minutes: int
    goals: int
    assists: int
    xg: float | None
    xa: float | None


@dataclass(frozen=True)
class SeasonRows:
    season_id: int
    season_label: str
    data_level: str
    source: str
    teams: list[str]
    players: list[PlayerRow]
    matches: list[MatchRow]
    shots: list[ShotRow]
    events: list[EventRow]
    stats: list[StatRow]


def ingest_url(env: Mapping[str, str]) -> str:
    """Return the ingest role's database URL, read from env."""
    url = env.get(INGEST_URL_VAR)
    if not url:
        raise SettingsError(f"{INGEST_URL_VAR} is not set")
    return url


def season_player_ids(conn: psycopg.Connection, season: str, name: str) -> list[int]:
    """Return the ids of the players of this exact name who played in the season.

    players.name is not unique, so the season picks the player.
    """
    return [
        player_id
        for (player_id,) in conn.execute(
            "SELECT DISTINCT p.id FROM players p"
            " JOIN player_match_stats pms ON pms.player_id = p.id"
            " JOIN matches m ON m.id = pms.match_id"
            " JOIN seasons s ON s.id = m.season_id"
            " WHERE p.name = %s AND s.label = %s ORDER BY p.id",
            (name, season),
        )
    ]


def name_candidates(
    conn: psycopg.Connection, rows: SeasonRows
) -> dict[int, dict[int, resolve.Candidate]]:
    """Return, for each team id, the players that a new source player can be by name.

    A candidate played for the team in the same season and has no alias row of the
    loading source: two records of one source are two players, whatever their names.
    """
    found: dict[int, dict[int, tuple[str, set[str]]]] = {}
    for player_id, name, team_id, source_name in conn.execute(
        "SELECT p.id, p.name, t.team_id, a.source_name FROM players p"
        " JOIN (SELECT DISTINCT pms.player_id, pms.team_id FROM player_match_stats pms"
        "  JOIN matches m ON m.id = pms.match_id WHERE m.season_id = %s) t"
        " ON t.player_id = p.id"
        # Fan nicknames are for questions; a source record is matched on source names.
        " LEFT JOIN player_aliases a ON a.player_id = p.id AND a.source <> %s"
        " WHERE NOT EXISTS (SELECT 1 FROM player_aliases own"
        "  WHERE own.player_id = p.id AND own.source = %s)",
        (rows.season_id, MANUAL_SOURCE, rows.source),
    ):
        _, names = found.setdefault(team_id, {}).setdefault(player_id, (name, {name}))
        if source_name is not None:
            names.add(source_name)
    return {
        team_id: {
            player_id: resolve.Candidate(player_id, name, tuple(sorted(names)))
            for player_id, (name, names) in players.items()
        }
        for team_id, players in found.items()
    }


def check_overrides(
    conn: psycopg.Connection,
    rows: SeasonRows,
    mine: Mapping[str, PlayerOverride],
    linked: Mapping[str, int],
) -> dict[str, int]:
    """Return the player id of each link override. Raise ValueError naming every problem.

    An override that disagrees with a link in the database stops the load: moving
    the rows of one player to another is a merge that a reload does better.
    """
    problems = []
    targets = {}
    for source_id, override in mine.items():
        if override.separate:
            continue
        found = season_player_ids(conn, override.season, override.player)
        where = f"override {rows.source} {source_id}: {override.player} ({override.season})"
        if not found:
            problems.append(f"{where}: no such player")
        elif len(found) > 1:
            problems.append(f"{where}: {len(found)} players have this name")
        else:
            targets[source_id] = found[0]

    # One player takes one record of a source: two records would share stats rows.
    claims: dict[int, set[str]] = {}
    for source_id, player_id in [*linked.items(), *targets.items()]:
        claims.setdefault(player_id, set()).add(source_id)
    for holders in claims.values():
        if len(holders) > 1 and (overridden := sorted(holders & targets.keys())):
            problems.append(
                f"records {rows.source} {', '.join(sorted(holders))} all link to"
                f" {mine[overridden[0]].player}: one player takes one record of a source"
            )

    linked_ids = [linked[source_id] for source_id in mine if source_id in linked]
    names = dict(conn.execute("SELECT id, name FROM players WHERE id = ANY(%s)", (linked_ids,)))
    # A player with an alias row of a second source was linked to it by name or override.
    joined = {
        player_id
        for (player_id,) in conn.execute(
            "SELECT DISTINCT player_id FROM player_aliases"
            " WHERE player_id = ANY(%s) AND source <> ALL(%s)",
            (linked_ids, [rows.source, MANUAL_SOURCE]),
        )
    }
    reload = "reload into a fresh database to apply it"
    for source_id, override in mine.items():
        current = linked.get(source_id)
        if current is None:
            continue
        if override.separate and current in joined:
            problems.append(
                f"override {rows.source} {source_id} is separate, but the database links it"
                f" to {names[current]}, a player of another source; {reload}"
            )
        elif source_id in targets and targets[source_id] != current:
            problems.append(
                f"override {rows.source} {source_id} links it to {override.player}, but the"
                f" database links it to {names[current]}; {reload}"
            )
    if problems:
        raise ValueError("; ".join(problems))
    return targets


def load_players(
    conn: psycopg.Connection,
    rows: SeasonRows,
    team_ids: Mapping[str, int],
    player_overrides: Mapping[tuple[str, str], PlayerOverride],
) -> tuple[dict[str, int], list[resolve.ReviewRow]]:
    """Give every source player a database id, and return the name links to review.

    A source player resolves in this order: an override in overrides.yaml always
    wins, then the alias row of the source's own player id (so a second run finds
    the same player), then the name within the same team and season. A player that
    none of these finds is new. A player who exists is left as it is, so a canonical
    name corrected by hand survives a second run.
    """
    linked = dict(
        conn.execute(
            "SELECT source_player_id, player_id FROM player_aliases WHERE source = %s",
            (rows.source,),
        ).fetchall()
    )
    mine = {
        source_id: override
        for (source, source_id), override in player_overrides.items()
        if source == rows.source
    }
    targets = check_overrides(conn, rows, mine, linked)
    # Read before any insert, so that a player of this load is never a candidate.
    candidates = name_candidates(conn, rows)
    teams: dict[str, list[str]] = {}
    for stat in rows.stats:
        if stat.team not in teams.setdefault(stat.player, []):
            teams[stat.player].append(stat.team)

    new = [player for player in rows.players if player.source_id not in linked]
    matches = {}
    for player in new:
        if player.source_id in mine:
            continue
        options = {
            candidate.player_id: candidate
            for team in teams.get(player.source_id, [])
            for candidate in candidates.get(team_ids[team], {}).values()
        }
        # The source's own name: it is the full name where the source has one.
        matches[player.source_id] = resolve.match_name(player.source_name, list(options.values()))
    taken = {player_id: source_id for source_id, player_id in [*linked.items(), *targets.items()]}
    matches = resolve.settle_claims(matches, taken)

    player_ids = dict(linked)
    review = []
    for player in new:
        match = matches.get(player.source_id)
        # An exact link is certain. A match with no candidate is a season's first source.
        if match is not None and match.outcome != "exact" and match.player is not None:
            review.append(
                resolve.ReviewRow(
                    player.source_id,
                    player.source_name,
                    tuple(teams.get(player.source_id, [])),
                    match,
                )
            )

        if player.source_id in targets:
            player_id = targets[player.source_id]
        elif match is not None and match.player_id is not None:
            player_id = match.player_id
        else:
            (player_id,) = conn.execute(
                "INSERT INTO players (name, position) VALUES (%s, %s) RETURNING id",
                (player.name, player.position),
            ).fetchone()
        conn.execute(
            "INSERT INTO player_aliases (player_id, source, source_player_id, source_name)"
            " VALUES (%s, %s, %s, %s)",
            (player_id, rows.source, player.source_id, player.source_name),
        )
        player_ids[player.source_id] = player_id
    return player_ids, review


def load(
    conn: psycopg.Connection,
    rows: SeasonRows,
    player_overrides: Mapping[tuple[str, str], PlayerOverride] | None = None,
) -> list[resolve.ReviewRow]:
    """Write one season with upserts, so that a second run changes nothing.

    Return the player name links to review. The caller owns the transaction:
    nothing is committed here.
    """
    conn.execute(
        "INSERT INTO seasons (id, label, data_level) VALUES (%s, %s, %s)"
        " ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label, data_level = EXCLUDED.data_level",
        (rows.season_id, rows.season_label, rows.data_level),
    )

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO teams (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(team,) for team in rows.teams],
        )
    team_ids = dict(
        conn.execute("SELECT name, id FROM teams WHERE name = ANY(%s)", (rows.teams,)).fetchall()
    )
    player_ids, review = load_players(conn, rows, team_ids, player_overrides or {})

    match_ids = {}
    for match in rows.matches:
        (match_ids[match.source_id],) = conn.execute(
            "INSERT INTO matches (season_id, match_date, home_team_id, away_team_id,"
            " home_goals, away_goals, venue, source, source_match_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (source, source_match_id) DO UPDATE SET"
            " season_id = EXCLUDED.season_id, match_date = EXCLUDED.match_date,"
            " home_team_id = EXCLUDED.home_team_id, away_team_id = EXCLUDED.away_team_id,"
            " home_goals = EXCLUDED.home_goals, away_goals = EXCLUDED.away_goals,"
            " venue = EXCLUDED.venue"
            " RETURNING id",
            (
                rows.season_id,
                match.match_date,
                team_ids[match.home_team],
                team_ids[match.away_team],
                match.home_goals,
                match.away_goals,
                match.venue,
                rows.source,
                match.source_id,
            ),
        ).fetchone()

    def player(source_id: str | None) -> int | None:
        return None if source_id is None else player_ids[source_id]

    # The ingest role cannot create temporary tables, so there is no staging table.
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO shots (match_id, player_id, team_id, minute, x, y, xg, outcome,"
            " body_part, situation, aerial_won, source, source_shot_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (source, source_shot_id) DO UPDATE SET"
            " match_id = EXCLUDED.match_id, player_id = EXCLUDED.player_id,"
            " team_id = EXCLUDED.team_id, minute = EXCLUDED.minute, x = EXCLUDED.x,"
            " y = EXCLUDED.y, xg = EXCLUDED.xg, outcome = EXCLUDED.outcome,"
            " body_part = EXCLUDED.body_part, situation = EXCLUDED.situation,"
            " aerial_won = EXCLUDED.aerial_won",
            [
                (
                    match_ids[shot.match],
                    player_ids[shot.player],
                    team_ids[shot.team],
                    shot.minute,
                    shot.x,
                    shot.y,
                    shot.xg,
                    shot.outcome,
                    shot.body_part,
                    shot.situation,
                    shot.aerial_won,
                    rows.source,
                    shot.source_id,
                )
                for shot in rows.shots
            ],
        )
        cur.executemany(
            "INSERT INTO events (match_id, player_id, team_id, type, minute, second, x, y,"
            " end_x, end_y, outcome, under_pressure, possession, recipient_id, period,"
            " pass_length, pass_type, shot_assist, goal_assist, aerial_won, duel_type,"
            " source_event_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,"
            " %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (source_event_id) DO UPDATE SET"
            " match_id = EXCLUDED.match_id, player_id = EXCLUDED.player_id,"
            " team_id = EXCLUDED.team_id, type = EXCLUDED.type, minute = EXCLUDED.minute,"
            " second = EXCLUDED.second, x = EXCLUDED.x, y = EXCLUDED.y,"
            " end_x = EXCLUDED.end_x, end_y = EXCLUDED.end_y, outcome = EXCLUDED.outcome,"
            " under_pressure = EXCLUDED.under_pressure, possession = EXCLUDED.possession,"
            " recipient_id = EXCLUDED.recipient_id, period = EXCLUDED.period,"
            " pass_length = EXCLUDED.pass_length, pass_type = EXCLUDED.pass_type,"
            " shot_assist = EXCLUDED.shot_assist, goal_assist = EXCLUDED.goal_assist,"
            " aerial_won = EXCLUDED.aerial_won, duel_type = EXCLUDED.duel_type",
            [
                (
                    match_ids[event.match],
                    player(event.player),
                    team_ids[event.team],
                    event.type,
                    event.minute,
                    event.second,
                    event.x,
                    event.y,
                    event.end_x,
                    event.end_y,
                    event.outcome,
                    event.under_pressure,
                    event.possession,
                    player(event.recipient),
                    event.period,
                    event.pass_length,
                    event.pass_type,
                    event.shot_assist,
                    event.goal_assist,
                    event.aerial_won,
                    event.duel_type,
                    event.source_id,
                )
                for event in rows.events
            ],
        )
        cur.executemany(
            "INSERT INTO player_match_stats (player_id, match_id, team_id, minutes, goals,"
            " assists, xg, xa)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (player_id, match_id) DO UPDATE SET"
            " team_id = EXCLUDED.team_id, minutes = EXCLUDED.minutes, goals = EXCLUDED.goals,"
            " assists = EXCLUDED.assists, xg = EXCLUDED.xg, xa = EXCLUDED.xa",
            [
                (
                    player_ids[stat.player],
                    match_ids[stat.match],
                    team_ids[stat.team],
                    stat.minutes,
                    stat.goals,
                    stat.assists,
                    stat.xg,
                    stat.xa,
                )
                for stat in rows.stats
            ],
        )
    return review


def table_counts(conn: psycopg.Connection) -> dict[str, int]:
    """Return the row count of every table a season load writes."""
    return {
        # The names come from the constant above, never from input.
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in SEASON_TABLES
    }


class SanityError(Exception):
    """The loaded season does not match the published facts."""


@dataclass(frozen=True)
class SeasonFacts:
    """Published facts of one team's league season, to prove a load against."""

    season: str
    team: str
    matches: int
    wins: int
    draws: int
    losses: int
    points: int
    goals_for: int
    top_scorer: str
    top_scorer_goals: int


def check_season(conn: psycopg.Connection, facts: SeasonFacts) -> None:
    """Raise SanityError naming every loaded total that differs from the facts."""
    matches, wins, draws, losses, goals_for = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE scored > conceded),"
        " count(*) FILTER (WHERE scored = conceded), count(*) FILTER (WHERE scored < conceded),"
        # From the match scores, so that own goals by the opponent count.
        " coalesce(sum(scored), 0)"
        " FROM ("
        "  SELECT CASE WHEN home.name = %(team)s THEN m.home_goals ELSE m.away_goals END"
        "   AS scored,"
        "  CASE WHEN home.name = %(team)s THEN m.away_goals ELSE m.home_goals END AS conceded"
        "  FROM matches m"
        "  JOIN seasons s ON s.id = m.season_id"
        "  JOIN teams home ON home.id = m.home_team_id"
        "  JOIN teams away ON away.id = m.away_team_id"
        "  WHERE s.label = %(season)s AND %(team)s IN (home.name, away.name)"
        " ) results",
        {"team": facts.team, "season": facts.season},
    ).fetchone()
    (goals,) = conn.execute(
        "SELECT coalesce(sum(pms.goals), 0)"
        " FROM player_match_stats pms"
        " JOIN matches m ON m.id = pms.match_id"
        " JOIN seasons s ON s.id = m.season_id"
        " JOIN players p ON p.id = pms.player_id"
        " WHERE s.label = %s AND p.name = %s",
        (facts.season, facts.top_scorer),
    ).fetchone()

    checks = [
        ("matches", facts.matches, matches),
        ("wins", facts.wins, wins),
        ("draws", facts.draws, draws),
        ("losses", facts.losses, losses),
        ("points", facts.points, 3 * wins + draws),
        ("goals for", facts.goals_for, goals_for),
        (f"{facts.top_scorer} goals", facts.top_scorer_goals, goals),
    ]
    mismatches = [
        f"{name}: expected {expected}, found {found}"
        for name, expected, found in checks
        if expected != found
    ]
    if mismatches:
        raise SanityError("; ".join(mismatches))
