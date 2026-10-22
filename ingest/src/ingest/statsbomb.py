"""Load Arsenal's 2003-04 league season from StatsBomb Open Data.

Run from the repository root:
    uv run --env-file .env python -m ingest.statsbomb
"""

import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ingest import command, load
from ingest.load import CoordinateError, EventRow, MatchRow, PlayerRow, SeasonRows, ShotRow, StatRow

RAW_DIR = Path(__file__).resolve().parents[2] / "raw" / "statsbomb"

COMPETITION_ID = 2
SEASON_ID = 44
TEAM = "Arsenal"
# Named by competition and season, as in the StatsBomb repository.
MATCHES_FILE = f"matches-{COMPETITION_ID}-{SEASON_ID}.json"

SOURCE = "statsbomb"
# seasons.id is not generated. The start year is a stable, readable id.
SEASON_DB_ID = 2003
SEASON_LABEL = "2003-04"
DATA_LEVEL = "EVENT"

PITCH_LENGTH = 120
PITCH_WIDTH = 80

# Both seasons share these five outcome values, so one chart legend fits both.
SHOT_OUTCOMES = {
    "Goal": "goal",
    "Saved": "saved",
    "Saved to Post": "saved",
    "Saved Off Target": "saved",
    "Blocked": "blocked",
    "Off T": "off target",
    "Wayward": "off target",
    "Post": "post",
}
# StatsBomb type name -> stored type, which is also the key of the event's detail record.
EVENT_TYPES = {
    "Pass": "pass",
    "Carry": "carry",
    "Pressure": "pressure",
    "Substitution": "substitution",
}
REGULAR_PERIODS = (1, 2)
SENDING_OFF_CARDS = ("Red Card", "Second Yellow")

# The Invincibles: unbeaten in the league, from the MVP plan's sanity asserts.
FACTS = load.SeasonFacts(
    season=SEASON_LABEL,
    team=TEAM,
    matches=38,
    wins=26,
    draws=12,
    losses=0,
    points=90,
    goals_for=73,
    top_scorer="Thierry Henry",
    top_scorer_goals=30,
)


@dataclass(frozen=True)
class RawSeason:
    """The cached StatsBomb records, with lineups and events keyed by match id."""

    matches: list[dict]
    lineups: dict[int, list[dict]]
    events: dict[int, list[dict]]


def cached(path: Path, fetch: Callable[[], dict]) -> list[dict]:
    """Return the records in the cache file. StatsBomb keys each response by id."""
    return list(command.cached_json(path, fetch).values())


def fetch_season(
    raw_dir: Path,
    fetch_matches: Callable[[], dict],
    fetch_lineups: Callable[[int], dict],
    fetch_events: Callable[[int], dict],
) -> RawSeason:
    """Read the season from raw_dir, downloading only the files that are missing."""
    matches = [
        match
        for match in cached(raw_dir / MATCHES_FILE, fetch_matches)
        if TEAM in (match["home_team"]["home_team_name"], match["away_team"]["away_team_name"])
    ]
    lineups, events = {}, {}
    for match in matches:
        match_id = match["match_id"]
        lineups[match_id] = cached(
            raw_dir / "lineups" / f"{match_id}.json", lambda m=match_id: fetch_lineups(m)
        )
        events[match_id] = cached(
            raw_dir / "events" / f"{match_id}.json", lambda m=match_id: fetch_events(m)
        )
    return RawSeason(matches, lineups, events)


def statsbomb_fetchers() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    # Imported here so that tests, which never use the network, do not load the client.
    from statsbombpy import sb

    return (
        lambda: sb.matches(competition_id=COMPETITION_ID, season_id=SEASON_ID, fmt="dict"),
        lambda match_id: sb.lineups(match_id=match_id, fmt="dict"),
        lambda match_id: sb.events(match_id=match_id, fmt="dict"),
    )


def point(location: list[float] | None, event_id: str) -> tuple[float | None, float | None]:
    """Return the pitch point of a StatsBomb location.

    StatsBomb already uses the 120 x 80 pitch with the team in possession attacking
    left to right, so the mapping is the identity. A location off the pitch is a data
    fault to look at, not a value to clamp.
    """
    if location is None:
        return None, None
    x, y = location[0], location[1]
    if not (0 <= x <= PITCH_LENGTH and 0 <= y <= PITCH_WIDTH):
        raise CoordinateError(f"event {event_id} is off the pitch: ({x}, {y})")
    return x, y


def shot_outcome(name: str) -> str:
    try:
        return SHOT_OUTCOMES[name]
    except KeyError:
        raise ValueError(f"unknown shot outcome: {name}") from None


def nominal_minute(minute: int, period: int | None) -> int:
    # Stoppage time belongs to the half it extends, so a half never runs past its end.
    return min(minute, 45 if period == 1 else 90)


def clock_minute(time: str | None, period: int | None) -> int:
    """Return the nominal match minute of a lineup time. No time means the final whistle."""
    if time is None:
        return 90
    return nominal_minute(int(time.split(":")[0]), period)


def minutes_played(positions: list[dict], left_at: int | None = None) -> int:
    """Return the nominal minutes a player was on the pitch, 0 for an unused substitute.

    left_at is the minute of the player's sending-off or Substitution event. The lineup
    spans record no sending-off and miss some substitutions, so it ends the minutes
    when it is earlier than the last span.
    """
    if not positions:
        return 0
    start = min(clock_minute(span["from"], span["from_period"]) for span in positions)
    end = max(clock_minute(span["to"], span["to_period"]) for span in positions)
    if left_at is not None:
        end = min(end, left_at)
    # A player who came on in stoppage time still made an appearance.
    return max(end - start, 1)


def lower_name(record: dict | None) -> str | None:
    return record["name"].lower() if record else None


def player_id(record: dict | None) -> str | None:
    return str(record["id"]) if record else None


def match_row(match: dict) -> MatchRow:
    stadium = match.get("stadium")
    return MatchRow(
        source_id=str(match["match_id"]),
        match_date=date.fromisoformat(match["match_date"]),
        home_team=match["home_team"]["home_team_name"],
        away_team=match["away_team"]["away_team_name"],
        # The score comes from the match record because own goals are not shots.
        home_goals=match["home_score"],
        away_goals=match["away_score"],
        venue=stadium["name"] if stadium else None,
    )


def shot_row(event: dict, match_id: str) -> ShotRow:
    shot = event["shot"]
    x, y = point(event["location"], event["id"])
    return ShotRow(
        source_id=event["id"],
        match=match_id,
        player=player_id(event["player"]),
        team=event["team"]["name"],
        minute=event["minute"],
        x=x,
        y=y,
        xg=shot["statsbomb_xg"],
        outcome=shot_outcome(shot["outcome"]["name"]),
        body_part=lower_name(shot.get("body_part")),
        situation=lower_name(shot.get("type")),
    )


def event_row(event: dict, match_id: str) -> EventRow:
    kind = EVENT_TYPES[event["type"]["name"]]
    detail = event.get(kind, {})
    x, y = point(event.get("location"), event["id"])
    end_x, end_y = point(detail.get("end_location"), event["id"])
    return EventRow(
        source_id=event["id"],
        match=match_id,
        player=player_id(event.get("player")),
        team=event["team"]["name"],
        type=kind,
        minute=event["minute"],
        second=event["second"],
        x=x,
        y=y,
        end_x=end_x,
        end_y=end_y,
        outcome=lower_name(detail.get("outcome")),
        under_pressure=event.get("under_pressure", False),
        possession=event.get("possession"),
        # A substitution stores the player who comes on as its recipient.
        recipient=player_id(detail.get("recipient") or detail.get("replacement")),
    )


def build_rows(raw: RawSeason) -> SeasonRows:
    """Turn the raw StatsBomb records into rows for the loader. No I/O."""
    matches = [match_row(match) for match in raw.matches]
    names: dict[str, tuple[str, str]] = {}
    positions: dict[str, Counter] = defaultdict(Counter)
    shots: list[ShotRow] = []
    events: list[EventRow] = []
    stats: list[StatRow] = []

    for match in raw.matches:
        match_id = str(match["match_id"])
        match_events = raw.events[match["match_id"]]

        left_at = {
            player_id(event["player"]): nominal_minute(event["minute"], event["period"])
            for event in match_events
            if event["type"]["name"] == "Substitution"
        }
        on_pitch: dict[str, tuple[str, int]] = {}
        for team in raw.lineups[match["match_id"]]:
            for entry in team["lineup"]:
                spans = entry["positions"]
                if not spans:
                    continue
                player = str(entry["player_id"])
                names[player] = (
                    entry.get("player_nickname") or entry["player_name"],
                    entry["player_name"],
                )
                positions[player][spans[0]["position"]] += 1
                for card in entry["cards"]:
                    if card["card_type"] in SENDING_OFF_CARDS:
                        left_at[player] = clock_minute(card["time"], card["period"])
                on_pitch[player] = (team["team_name"], minutes_played(spans, left_at.get(player)))

        passers = {
            event["id"]: player_id(event["player"])
            for event in match_events
            if event["type"]["name"] == "Pass"
        }
        goals: Counter = Counter()
        assists: Counter = Counter()
        xg: dict[str, float] = defaultdict(float)
        xa: dict[str, float] = defaultdict(float)

        for event in match_events:
            kind = event["type"]["name"]
            if kind == "Shot" and event["period"] in REGULAR_PERIODS:
                shot = shot_row(event, match_id)
                shots.append(shot)
                xg[shot.player] += shot.xg
                goals[shot.player] += shot.outcome == "goal"
                key_pass = event["shot"].get("key_pass_id")
                if key_pass in passers:
                    xa[passers[key_pass]] += shot.xg
            elif kind in EVENT_TYPES:
                row = event_row(event, match_id)
                events.append(row)
                if event.get("pass", {}).get("goal_assist"):
                    assists[row.player] += 1

        credited = set(goals) | set(assists) | set(xg) | set(xa)
        if unknown := credited - set(on_pitch):
            # Their numbers would vanish without a stats row, so stop instead.
            raise ValueError(f"match {match_id}: players {sorted(unknown)} are not in the lineup")

        for player, (team_name, minutes) in on_pitch.items():
            stats.append(
                StatRow(
                    player=player,
                    match=match_id,
                    team=team_name,
                    minutes=minutes,
                    goals=goals[player],
                    assists=assists[player],
                    xg=xg.get(player, 0.0),
                    xa=xa.get(player, 0.0),
                )
            )

    players = [
        PlayerRow(
            source_id=player,
            name=name,
            source_name=source_name,
            # The position of the most matches; a tie takes the first by name.
            position=min(positions[player], key=lambda p: (-positions[player][p], p)),
        )
        for player, (name, source_name) in names.items()
    ]
    return SeasonRows(
        season_id=SEASON_DB_ID,
        season_label=SEASON_LABEL,
        data_level=DATA_LEVEL,
        source=SOURCE,
        teams=sorted({team for m in matches for team in (m.home_team, m.away_team)}),
        players=players,
        matches=matches,
        shots=shots,
        events=events,
        stats=stats,
    )


def main() -> int:
    return command.run(
        lambda: build_rows(fetch_season(RAW_DIR, *statsbomb_fetchers())),
        FACTS,
    )


if __name__ == "__main__":
    sys.exit(main())
