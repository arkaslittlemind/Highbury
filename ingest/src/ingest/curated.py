"""Load the hand-written reference data: player aliases and the data catalog.

Both seasons must be loaded first. Run from the repository root:
    uv run --env-file .env python -m ingest.curated
"""

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml

from ingest import command, load
from ingest.migrate import SettingsError

ALIASES_FILE = Path(__file__).resolve().parents[2] / "aliases.yaml"

# The season loaders write one alias row per player with their own source name.
SOURCE = "manual"

STATSBOMB = "StatsBomb Open Data"
UNDERSTAT = "Understat"
NO_EVENTS = "Understat has shots but no pass, carry, or pressure events."

# (season label, metric, available, source, notes). The agent reads these rows
# before a claim about one season, so each note is written for the model.
CATALOG = (
    ("2003-04", "results", True, STATSBOMB, "All 38 Arsenal league matches: date, teams, score."),
    ("2003-04", "shots", True, STATSBOMB, "Every shot of both teams, with pitch coordinates."),
    (
        "2003-04",
        "xg",
        True,
        STATSBOMB,
        "StatsBomb xG model. It is not the Understat model of 2025-26, so say this"
        " caveat in a comparison of xG between the two seasons.",
    ),
    (
        "2003-04",
        "player_stats",
        True,
        STATSBOMB,
        "Minutes, goals, and assists for each player in each match.",
    ),
    ("2003-04", "passes", True, STATSBOMB, "Every pass, with start and end coordinates."),
    ("2003-04", "pressures", True, STATSBOMB, "Every pressure event, with coordinates."),
    (
        "2003-04",
        "pass_networks",
        True,
        STATSBOMB,
        "Built from the passes of one match: who passed to whom, and how often.",
    ),
    ("2025-26", "results", True, UNDERSTAT, "All 38 Arsenal league matches: date, teams, score."),
    ("2025-26", "shots", True, UNDERSTAT, "Every shot of both teams, with pitch coordinates."),
    (
        "2025-26",
        "xg",
        True,
        UNDERSTAT,
        "Understat xG model. It is not the StatsBomb model of 2003-04, so say this"
        " caveat in a comparison of xG between the two seasons. Match xG is the sum"
        " of shot xG, which can be above the match xG that Understat publishes.",
    ),
    (
        "2025-26",
        "player_stats",
        True,
        UNDERSTAT,
        "Minutes, goals, and assists for each player in each match.",
    ),
    (
        "2025-26",
        "passes",
        False,
        None,
        f"{NO_EVENTS} Offer the player's shot map for 2025-26 instead.",
    ),
    (
        "2025-26",
        "pressures",
        False,
        None,
        f"{NO_EVENTS} Offer shots or xG for 2025-26, or pressures for 2003-04, instead.",
    ),
    (
        "2025-26",
        "pass_networks",
        False,
        None,
        f"{NO_EVENTS} Offer a 2003-04 pass network or a 2025-26 shot map instead.",
    ),
)


class CuratedError(Exception):
    """The alias file or the database does not fit the curated data."""


@dataclass(frozen=True)
class AliasEntry:
    season: str
    player: str
    aliases: tuple[str, ...]


def same(text: str) -> str:
    """Return the form in which two aliases are one alias."""
    return text.strip().casefold()


def parse_aliases(text: str) -> list[AliasEntry]:
    """Read the alias file. Raise CuratedError that names every problem in it."""
    try:
        records = yaml.safe_load(text)
    except yaml.YAMLError as error:
        # The full text of a YAML error has several lines. The command prints one.
        problem = getattr(error, "problem", None) or type(error).__name__
        mark = getattr(error, "problem_mark", None)
        where = f" at line {mark.line + 1}" if mark else ""
        raise CuratedError(f"the alias file is not valid YAML: {problem}{where}") from error
    if not isinstance(records, list) or not records:
        raise CuratedError("the alias file must be a list of entries")

    problems = []
    entries = []
    listed: set[tuple[str, str]] = set()
    owners: dict[str, tuple[str, str]] = {}
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            problems.append(f"entry {number}: must have season, player, and aliases")
            continue
        fields = {}
        for field in ("season", "player"):
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                fields[field] = value.strip()
            else:
                problems.append(f"entry {number}: {field} is missing")
        if len(fields) < 2:
            continue
        season, player = fields["season"], fields["player"]

        if (season, player) in listed:
            problems.append(f"{player} ({season}) is listed twice")
            continue
        listed.add((season, player))

        aliases = record.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            problems.append(f"{player}: has no alias")
            continue
        kept = []
        for alias in aliases:
            if not isinstance(alias, str):
                problems.append(f"{player}: alias {alias!r} is not text")
                continue
            if not alias.strip():
                problems.append(f"{player}: has an empty alias")
                continue
            alias = alias.strip()
            # The season is part of the owner: two players can have one name.
            owner = owners.setdefault(same(alias), (season, player))
            if owner != (season, player):
                problems.append(f"alias {alias!r} is under {owner[1]} and {player}")
            elif same(alias) in map(same, kept):
                problems.append(f"{player}: alias {alias!r} is listed twice")
            else:
                kept.append(alias)
        entries.append(AliasEntry(season, player, tuple(kept)))

    if problems:
        raise CuratedError("; ".join(problems))
    return entries


def load_aliases(conn: psycopg.Connection, entries: list[AliasEntry]) -> None:
    """Make the manual aliases in the database equal to the entries.

    Every problem is found before the first write. The caller owns the transaction.
    """
    # Every name a player already has. An alias that is also the name of a second
    # player would point to two players.
    names: dict[str, set[int]] = {}
    for player_id, name in conn.execute(
        "SELECT id, name FROM players"
        " UNION ALL SELECT player_id, source_name FROM player_aliases WHERE source <> %s",
        (SOURCE,),
    ):
        names.setdefault(same(name), set()).add(player_id)

    problems = []
    rows = []
    claimed: dict[str, int] = {}
    for entry in entries:
        # players.name is not unique, so the season picks the player.
        found = conn.execute(
            "SELECT DISTINCT p.id FROM players p"
            " JOIN player_match_stats pms ON pms.player_id = p.id"
            " JOIN matches m ON m.id = pms.match_id"
            " JOIN seasons s ON s.id = m.season_id"
            " WHERE p.name = %s AND s.label = %s",
            (entry.player, entry.season),
        ).fetchall()
        if not found:
            problems.append(f"{entry.player} ({entry.season}): no such player")
            continue
        if len(found) > 1:
            problems.append(f"{entry.player} ({entry.season}): {len(found)} players have this name")
            continue
        ((player_id,),) = found
        for alias in entry.aliases:
            if names.get(same(alias), set()) - {player_id}:
                problems.append(
                    f"{entry.player} ({entry.season}): alias {alias!r} is the name of"
                    " another player"
                )
            elif claimed.setdefault(same(alias), player_id) != player_id:
                problems.append(
                    f"{entry.player} ({entry.season}): alias {alias!r} is also the alias"
                    " of another player"
                )
            rows.append((player_id, SOURCE, alias))
    if problems:
        raise CuratedError("; ".join(problems))

    # The file is the source of truth. An upsert would keep an alias that was
    # removed from the file.
    conn.execute("DELETE FROM player_aliases WHERE source = %s", (SOURCE,))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO player_aliases (player_id, source, source_name) VALUES (%s, %s, %s)",
            rows,
        )


def load_catalog(conn: psycopg.Connection) -> None:
    """Make data_catalog equal to CATALOG. The caller owns the transaction."""
    labels = sorted({label for label, *_ in CATALOG})
    season_ids = dict(
        conn.execute("SELECT label, id FROM seasons WHERE label = ANY(%s)", (labels,)).fetchall()
    )
    if missing := [label for label in labels if label not in season_ids]:
        raise CuratedError("; ".join(f"season {label} is not loaded" for label in missing))

    conn.execute("DELETE FROM data_catalog")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO data_catalog (season_id, metric, available, source, notes)"
            " VALUES (%s, %s, %s, %s, %s)",
            [(season_ids[label], *row) for label, *row in CATALOG],
        )


def run(path: Path = ALIASES_FILE, env: Mapping[str, str] = os.environ) -> int:
    """Load the aliases and the catalog in one transaction and return the exit code."""
    try:
        url = load.ingest_url(env)
        entries = parse_aliases(path.read_text(encoding="utf-8"))
        # The connection block commits on a clean exit and rolls back on an error,
        # so the aliases and the catalog are both loaded or both left as they were.
        with psycopg.connect(url, connect_timeout=command.CONNECT_TIMEOUT_SECONDS) as conn:
            load_aliases(conn, entries)
            load_catalog(conn)
    except SettingsError as error:
        print(f"Settings error: {error}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as error:
        print(f"Cannot read the alias file: {error}", file=sys.stderr)
        return 1
    except CuratedError as error:
        print(f"Curated data is not valid, nothing was loaded: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        # The text of a client-side error can repeat the URL, password included, so
        # only the server's own message is printed.
        message = error.diag.message_primary or type(error).__name__
        print(f"Load failed, nothing was loaded: {message}", file=sys.stderr)
        return 1

    aliases = sum(len(entry.aliases) for entry in entries)
    print(f"player_aliases: {aliases} aliases for {len(entries)} players")
    print(f"data_catalog: {len(CATALOG)}")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
