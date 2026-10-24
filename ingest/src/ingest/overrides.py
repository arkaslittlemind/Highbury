"""Read ingest/overrides.yaml: the team spellings, the player overrides, and the fan nicknames.

The file is written by hand and always wins over what the resolver finds.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

OVERRIDES_FILE = Path(__file__).resolve().parents[2] / "overrides.yaml"
SECTIONS = ("teams", "players", "nicknames")


class OverridesError(Exception):
    """The overrides file cannot be read or does not fit its rules."""


@dataclass(frozen=True)
class AliasEntry:
    season: str
    player: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class PlayerOverride:
    source: str
    source_id: str
    # Both None for a separate entry: the record never links by name.
    season: str | None
    player: str | None

    @property
    def separate(self) -> bool:
        return self.player is None


@dataclass(frozen=True)
class Overrides:
    # Source spelling to the canonical teams.name.
    teams: dict[str, str]
    # (source, source_id) to the override of that source record.
    players: dict[tuple[str, str], PlayerOverride]
    nicknames: list[AliasEntry]


def team_name(spelling: str, teams: Mapping[str, str]) -> str:
    """Return the canonical name of a source spelling. A spelling not in teams is one."""
    return teams.get(spelling, spelling)


def same(text: str) -> str:
    """Return the form in which two names are one name."""
    return text.strip().casefold()


def text_fields(
    record: dict, fields: tuple[str, ...], where: str, problems: list[str]
) -> dict[str, str]:
    """Return the fields of record that are text, and name each one that is not."""
    found = {}
    for field in fields:
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            found[field] = value.strip()
        else:
            problems.append(f"{where}: {field} is missing")
    return found


def parse_teams(records: list, problems: list[str]) -> dict[str, str]:
    teams: dict[str, str] = {}
    listed: set[str] = set()
    entries = []
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            problems.append(f"teams entry {number}: must have team and spellings")
            continue
        fields = text_fields(record, ("team",), f"teams entry {number}", problems)
        if not fields:
            continue
        team = fields["team"]
        if same(team) in listed:
            problems.append(f"team {team} is listed twice")
            continue
        listed.add(same(team))
        spellings = record.get("spellings")
        if not isinstance(spellings, list) or not spellings:
            problems.append(f"{team}: has no spelling")
            continue
        entries.append((team, spellings))

    owners: dict[str, str] = {}
    for team, spellings in entries:
        for spelling in spellings:
            if not isinstance(spelling, str) or not spelling.strip():
                problems.append(f"{team}: spelling {spelling!r} is not text")
                continue
            spelling = spelling.strip()
            owner = owners.get(same(spelling))
            if owner is not None and owner != team:
                problems.append(f"spelling {spelling!r} is under {owner} and {team}")
            elif owner == team:
                problems.append(f"{team}: spelling {spelling!r} is listed twice")
            elif same(spelling) in listed - {same(team)}:
                # A map that chains would send one club through two names.
                problems.append(f"{team}: spelling {spelling!r} is the name of another team")
            else:
                owners[same(spelling)] = team
                teams[spelling] = team
    return teams


def parse_players(records: list, problems: list[str]) -> dict[tuple[str, str], PlayerOverride]:
    players: dict[tuple[str, str], PlayerOverride] = {}
    for number, record in enumerate(records, start=1):
        where = f"players entry {number}"
        if not isinstance(record, dict):
            problems.append(f"{where}: must have source, source_id, and a player or separate")
            continue
        source_id = record.get("source_id")
        if isinstance(source_id, int | float):
            # YAML reads 0123 as 123, so an unquoted id can change.
            problems.append(f"{where}: source_id {source_id} is a number; quote it")
            continue
        fields = text_fields(record, ("source", "source_id"), where, problems)
        if len(fields) < 2:
            continue
        key = (fields["source"], fields["source_id"])

        separate = record.get("separate")
        if separate is None:
            target = text_fields(record, ("season", "player"), where, problems)
            if len(target) < 2:
                continue
            override = PlayerOverride(*key, target["season"], target["player"])
        elif separate is not True:
            problems.append(f"{where}: separate must be true")
            continue
        elif "season" in record or "player" in record:
            problems.append(f"{where}: has both a player and separate")
            continue
        else:
            override = PlayerOverride(*key, None, None)

        if key in players:
            problems.append(f"players: {key[0]} {key[1]} is listed twice")
            continue
        players[key] = override
    return players


def parse_nicknames(records: list, problems: list[str]) -> list[AliasEntry]:
    entries = []
    listed: set[tuple[str, str]] = set()
    owners: dict[str, tuple[str, str]] = {}
    for number, record in enumerate(records, start=1):
        where = f"nicknames entry {number}"
        if not isinstance(record, dict):
            problems.append(f"{where}: must have season, player, and aliases")
            continue
        fields = text_fields(record, ("season", "player"), where, problems)
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
    return entries


def parse(text: str) -> Overrides:
    """Read the overrides file. Raise OverridesError that names every problem in it."""
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as error:
        # The full text of a YAML error has several lines. The commands print one.
        problem = getattr(error, "problem", None) or type(error).__name__
        mark = getattr(error, "problem_mark", None)
        where = f" at line {mark.line + 1}" if mark else ""
        raise OverridesError(f"the overrides file is not valid YAML: {problem}{where}") from error
    if not isinstance(document, dict):
        raise OverridesError("the overrides file must have the sections teams, players, nicknames")

    problems = [f"unknown section {key!r}" for key in document if key not in SECTIONS]
    sections = {}
    for name in SECTIONS:
        if name not in document:
            problems.append(f"section {name} is missing")
        elif not isinstance(document[name], list):
            problems.append(f"section {name} must be a list")
        else:
            sections[name] = document[name]
    if problems:
        raise OverridesError("; ".join(problems))

    overrides = Overrides(
        teams=parse_teams(sections["teams"], problems),
        players=parse_players(sections["players"], problems),
        nicknames=parse_nicknames(sections["nicknames"], problems),
    )
    if problems:
        raise OverridesError("; ".join(problems))
    return overrides


def read(path: Path = OVERRIDES_FILE) -> Overrides:
    """Read and check the overrides file at path."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise OverridesError(f"cannot read {path.name}: {error}") from error
    return parse(text)
