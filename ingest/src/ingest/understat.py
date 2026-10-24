"""Load Arsenal's 2025-26 league season from Understat.

Run from the repository root:
    uv run --env-file .env python -m ingest.understat
"""

import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from ingest import command, load, overrides
from ingest.load import CoordinateError, MatchRow, PlayerRow, SeasonRows, ShotRow, StatRow

RAW_DIR = Path(__file__).resolve().parents[2] / "raw" / "understat"

BASE_URL = "https://understat.com"
TEAM = "Arsenal"
# Understat names a season by the year it starts in.
UNDERSTAT_SEASON = 2025
TEAM_FILE = f"team-{TEAM}-{UNDERSTAT_SEASON}.json"

REQUEST_TIMEOUT_SECONDS = 30
# Understat is a small site that many people use. One request at a time, with a pause.
PAUSE_SECONDS = 1

SOURCE = "understat"
# seasons.id is not generated. The start year is a stable, readable id.
SEASON_DB_ID = 2025
SEASON_LABEL = "2025-26"
# Understat has shots but no pass, carry, or pressure events.
DATA_LEVEL = "SHOT"

PITCH_LENGTH = 120
PITCH_WIDTH = 80

SIDES = ("h", "a")
OWN_GOAL = "OwnGoal"
SUBSTITUTE = "Sub"

# The stored values are the ones the 2003-04 load uses, so one legend fits both seasons.
SHOT_OUTCOMES = {
    "Goal": "goal",
    "SavedShot": "saved",
    "BlockedShot": "blocked",
    "MissedShots": "off target",
    "ShotOnPost": "post",
}
BODY_PARTS = {
    "RightFoot": "right foot",
    "LeftFoot": "left foot",
    "Head": "head",
    "OtherBodyPart": "other",
}
SITUATIONS = {
    "OpenPlay": "open play",
    "Penalty": "penalty",
    "DirectFreekick": "free kick",
    "FromCorner": "corner",
    "SetPiece": "set piece",
}

# The published 2025-26 league table and Arsenal scorer list, as the project owner
# gave them on 2026-10-11. They do not come from Understat, so that the check is
# against a second source. The scorer's name is the one Understat stores.
FACTS = load.SeasonFacts(
    season=SEASON_LABEL,
    team=TEAM,
    matches=38,
    wins=26,
    draws=7,
    losses=5,
    points=85,
    goals_for=71,
    top_scorer="Viktor Gyokeres",
    top_scorer_goals=14,
)


@dataclass(frozen=True)
class RawSeason:
    """The cached Understat records: the season's matches and the data of each match."""

    matches: list[dict]
    match_data: dict[str, dict]


def fetch_season(
    raw_dir: Path,
    fetch_team: Callable[[], dict],
    fetch_match: Callable[[str], dict],
) -> RawSeason:
    """Read the season from raw_dir, downloading only the files that are missing."""
    team = command.cached_json(raw_dir / TEAM_FILE, fetch_team)
    # A fixture that has no result yet has no shots and no rosters.
    matches = [match for match in team["dates"] if match["isResult"]]
    match_data = {
        match["id"]: command.cached_json(
            raw_dir / "matches" / f"{match['id']}.json", lambda m=match["id"]: fetch_match(m)
        )
        for match in matches
    }
    return RawSeason(matches, match_data)


def understat_fetchers() -> tuple[Callable[[], Any], Callable[[str], Any]]:
    """Return the two functions that download from understat.com."""
    client = httpx.Client(
        base_url=BASE_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        # The site answers its data requests only when they look like its own page's.
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    def get(path: str) -> Any:
        try:
            response = client.get(path)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise command.FetchError(f"cannot download {path}: {type(error).__name__}") from error
        time.sleep(PAUSE_SECONDS)
        return response.json()

    return (
        lambda: get(f"/getTeamData/{TEAM}/{UNDERSTAT_SEASON}"),
        lambda match_id: get(f"/getMatchData/{match_id}"),
    )


def point(x: str, y: str, shot_id: str) -> tuple[float, float]:
    """Return the pitch point of an Understat shot on the 120 x 80 pitch.

    Understat gives X and Y from 0 to 1, with the shooter attacking towards X = 1.
    Its Y counts from the attacker's right, and the stored pitch counts y from the
    attacker's left, as StatsBomb does. Thus Y is mirrored. A value outside 0 to 1
    is a data fault to look at, not a value to clamp.
    """
    scaled_x, scaled_y = float(x), float(y)
    if not (0 <= scaled_x <= 1 and 0 <= scaled_y <= 1):
        raise CoordinateError(f"shot {shot_id} is off the pitch: ({x}, {y})")
    return scaled_x * PITCH_LENGTH, (1 - scaled_y) * PITCH_WIDTH


def stored(table: dict[str, str], value: str, kind: str, shot_id: str) -> str:
    try:
        return table[value]
    except KeyError:
        raise ValueError(f"shot {shot_id} has an unknown {kind}: {value}") from None


def shot_row(shot: dict, match_id: str, team: str) -> ShotRow:
    x, y = point(shot["X"], shot["Y"], shot["id"])
    return ShotRow(
        source_id=shot["id"],
        match=match_id,
        player=shot["player_id"],
        team=team,
        minute=int(shot["minute"]),
        x=x,
        y=y,
        xg=float(shot["xG"]),
        outcome=stored(SHOT_OUTCOMES, shot["result"], "result", shot["id"]),
        body_part=stored(BODY_PARTS, shot["shotType"], "shot type", shot["id"]),
        situation=stored(SITUATIONS, shot["situation"], "situation", shot["id"]),
    )


def stat_row(entry: dict, match_id: str, team: str) -> StatRow:
    # Understat's own match values. They are not computed again from the shots.
    return StatRow(
        player=entry["player_id"],
        match=match_id,
        team=team,
        minutes=int(entry["time"]),
        goals=int(entry["goals"]),
        assists=int(entry["assists"]),
        xg=float(entry["xG"]),
        xa=float(entry["xA"]),
    )


def build_rows(raw: RawSeason, team_names: Mapping[str, str]) -> SeasonRows:
    """Turn the raw Understat records into rows for the loader. No I/O.

    team_names maps an Understat title to the canonical club name. A club that is
    already in the database from 2003-04 keeps that name, so that one club is one
    row in teams. Every other club keeps the Understat title.
    """
    matches: list[MatchRow] = []
    shots: list[ShotRow] = []
    stats: list[StatRow] = []
    names: dict[str, str] = {}
    positions: dict[str, Counter] = defaultdict(Counter)

    for match in raw.matches:
        match_id = match["id"]
        data = raw.match_data[match_id]
        teams = {side: overrides.team_name(match[side]["title"], team_names) for side in SIDES}
        matches.append(
            MatchRow(
                source_id=match_id,
                # The date part of Understat's match time, as given.
                match_date=date.fromisoformat(match["datetime"][:10]),
                home_team=teams["h"],
                away_team=teams["a"],
                home_goals=int(match["goals"]["h"]),
                away_goals=int(match["goals"]["a"]),
                venue=None,
            )
        )

        rosters = {side: list(data["rosters"][side].values()) for side in SIDES}
        for side, opponent in (("h", "a"), ("a", "h")):
            for entry in rosters[side]:
                player = entry["player_id"]
                names[player] = entry["player"]
                if entry["position"] != SUBSTITUTE:
                    positions[player][entry["position"]] += 1
                stats.append(stat_row(entry, match_id, teams[side]))

            in_roster = {entry["player_id"] for entry in rosters[side]}
            for shot in data["shots"][side]:
                # An own goal is not a shot, as in the 2003-04 data. The match score
                # counts it, so the goals in the shots can differ from the score.
                if shot["result"] == OWN_GOAL:
                    continue
                if shot["player_id"] not in in_roster:
                    raise ValueError(
                        f"match {match_id}: the player of shot {shot['id']} is not in the roster"
                    )
                shots.append(shot_row(shot, match_id, teams[side]))

            scored = sum(int(entry["goals"]) for entry in rosters[side])
            own_goals = sum(int(entry["own_goals"]) for entry in rosters[opponent])
            if scored + own_goals != int(match["goals"][side]):
                # Player goals that do not explain the score would give wrong totals.
                raise ValueError(
                    f"match {match_id}: {teams[side]} has {scored} player goals and"
                    f" {own_goals} own goals for a score of {match['goals'][side]}"
                )

    players = [
        PlayerRow(
            source_id=player,
            name=name,
            source_name=name,
            # The position of the most starts; a tie takes the first by name. A player
            # who only came on as a substitute has no position.
            position=min(positions[player], key=lambda p: (-positions[player][p], p), default=None),
        )
        for player, name in names.items()
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
        events=[],
        stats=stats,
    )


def main() -> int:
    return command.run(
        lambda: build_rows(fetch_season(RAW_DIR, *understat_fetchers()), overrides.read().teams),
        FACTS,
    )


if __name__ == "__main__":
    sys.exit(main())
