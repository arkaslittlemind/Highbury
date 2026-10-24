"""Match a source player to a canonical player by name, and write the review report.

No database access: the loader reads the candidates and acts on the result.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from rapidfuzz import fuzz

REVIEW_DIR = Path(__file__).resolve().parents[2] / "review"

# NFKD splits é into e and a combining mark, but these letters have no parts, so
# without the table Ødegaard would never equal Odegaard.
LETTERS = str.maketrans(
    {
        "ø": "o",
        "Ø": "O",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "ß": "ss",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ð": "d",
        "Ð": "D",
        "þ": "th",
        "Þ": "TH",
        "ı": "i",
    }
)
SEPARATORS = re.compile(r"[\W_]+")

# A name link needs a high score and a clear lead. A wrong link would join the
# numbers of two players, so a close second sends the record to review instead.
CUTOFF = 90
LEAD = 10

Outcome = Literal["exact", "fuzzy", "ambiguous", "unmatched"]


@dataclass(frozen=True)
class Candidate:
    player_id: int
    player: str
    # The canonical name and the names that the sources give. Not the fan nicknames.
    names: tuple[str, ...]


@dataclass(frozen=True)
class NameMatch:
    outcome: Outcome
    # Set only for exact and fuzzy: the player to link the record to.
    player_id: int | None = None
    # The closest candidate, also when the record is not linked to it.
    player: str | None = None
    score: float | None = None
    runner_up: str | None = None
    runner_up_score: float | None = None

    @property
    def linked(self) -> bool:
        return self.player_id is not None


@dataclass(frozen=True)
class ReviewRow:
    source_id: str
    source_name: str
    teams: tuple[str, ...]
    match: NameMatch


def normalize(name: str) -> str:
    """Return the form in which two spellings of one name are equal."""
    decomposed = unicodedata.normalize("NFKD", name.translate(LETTERS))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return SEPARATORS.sub(" ", plain.casefold()).strip()


def match_name(name: str, candidates: Sequence[Candidate]) -> NameMatch:
    """Find the candidate that a source name means, or say why there is none."""
    key = normalize(name)
    # Sorted, so that a tie gives the same result whatever the order of the rows.
    ordered = sorted(candidates, key=lambda candidate: candidate.player_id)
    if not ordered:
        return NameMatch("unmatched")

    exact = [c for c in ordered if key in {normalize(text) for text in c.names}]
    if len(exact) == 1:
        return NameMatch("exact", exact[0].player_id, exact[0].player, 100.0)
    if len(exact) > 1:
        return NameMatch("ambiguous", None, exact[0].player, 100.0, exact[1].player, 100.0)

    scored = sorted(
        ((max(fuzz.token_set_ratio(key, normalize(text)) for text in c.names), c) for c in ordered),
        # sorted is stable, so equal scores stay in player_id order.
        key=lambda pair: -pair[0],
    )
    (score, best), *rest = scored
    runner_up, runner_up_score = (rest[0][1].player, rest[0][0]) if rest else (None, None)
    if score < CUTOFF:
        return NameMatch("unmatched", None, best.player, score, runner_up, runner_up_score)
    if runner_up_score is not None and score - runner_up_score < LEAD:
        return NameMatch("ambiguous", None, best.player, score, runner_up, runner_up_score)
    return NameMatch("fuzzy", best.player_id, best.player, score, runner_up, runner_up_score)


def settle_claims(
    matches: Mapping[str, NameMatch], taken: Mapping[int, str]
) -> dict[str, NameMatch]:
    """Unlink each name match that would give one player two records of one source.

    matches maps a source id to its match; taken maps a player id to the source id
    that already has it, by an older record or by an override. Two records of one
    source are two players, and their stats rows would share one key. Among new
    records that pick the same free player, one exact match wins; otherwise none
    links. The losers become new players, so the result does not depend on order.
    """
    claims: dict[int, list[str]] = {}
    for source_id, match in matches.items():
        if match.player_id is not None:
            claims.setdefault(match.player_id, []).append(source_id)
    settled = dict(matches)
    for player_id, source_ids in claims.items():
        exact = [source_id for source_id in source_ids if matches[source_id].outcome == "exact"]
        if player_id in taken:
            winners = []
        elif len(source_ids) == 1:
            winners = source_ids
        else:
            winners = exact if len(exact) == 1 else []
        for source_id in source_ids:
            if source_id not in winners:
                settled[source_id] = replace(
                    matches[source_id], outcome="ambiguous", player_id=None
                )
    return settled


def cell(value: object) -> str:
    """Return a value as the text of one Markdown table cell."""
    if value is None:
        return ""
    if isinstance(value, float):
        # One decimal, so that 89.6 does not read as a pass of the cutoff of 90.
        value = f"{value:.1f}"
    # Source names are outside text: a pipe or a line break would break the table.
    return " ".join(str(value).split()).replace("|", "\\|")


def render_report(source: str, season: str, rows: Sequence[ReviewRow]) -> str:
    """Return the review report of one season load as Markdown."""
    lines = [f"# Entity review: {source} {season}", ""]
    if not rows:
        return "\n".join([*lines, "No records need review.", ""])
    lines += [
        "Each row is a source player whose name link is not certain. Linked rows are"
        " joined to the player; the others became a new player. Add an entry to"
        " `players` in `ingest/overrides.yaml` to change either.",
        "",
        "| Source ID | Source name | Team | Outcome | Closest player | Score | Runner-up"
        " | Runner-up score |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        match = row.match
        outcome = f"{match.outcome}: {'linked' if match.linked else 'new player'}"
        values = (
            row.source_id,
            row.source_name,
            ", ".join(row.teams),
            outcome,
            match.player,
            match.score,
            match.runner_up,
            match.runner_up_score,
        )
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    return "\n".join([*lines, ""])


def write_report(path: Path, text: str) -> None:
    """Replace the report file, so that an old report never looks current."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
