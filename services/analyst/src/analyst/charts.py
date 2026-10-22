"""Chart specs: what a chart shows, as data. The web app decides how it looks.

This module reads no database. tools.build_chart gets the rows and gives them here.
"""

import math
from collections.abc import Sequence
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

ChartType = Literal["shot_map", "compare_bars", "pass_network", "xg_timeline"]

MAX_TITLE = 120

PitchX = Annotated[float, Field(ge=0, le=120)]
PitchY = Annotated[float, Field(ge=0, le=80)]
Text = Annotated[str, Field(min_length=1)]
# The minute columns of the views hold a match minute, stoppage time included.
Minute = Annotated[int, Field(ge=0, le=130)]
ShotXg = Annotated[float, Field(ge=0, le=1)]
# Every match in the database is an Arsenal match, so a timeline puts Arsenal first.
ARSENAL = "Arsenal"


class ChartRejected(Exception):
    """The request or the rows do not make the chart. The text says why."""


class Spec(BaseModel):
    # Strict: a text or a boolean in a number column is an error, not a number.
    model_config = ConfigDict(strict=True, allow_inf_nan=False)


class Shot(Spec):
    x: PitchX
    y: PitchY
    xg: ShotXg
    outcome: Text
    minute: Annotated[int, Field(ge=0)]
    opponent: Text
    player: str | None = None
    season: str | None = None
    match_date: str | None = None


class ShotMap(Spec):
    type: Literal["shot_map"] = "shot_map"
    id: str
    title: str
    shots: list[Shot]


class Series(Spec):
    player: Text
    season: Text


class Metric(Spec):
    name: str
    # values[i] belongs to series[i].
    values: Annotated[list[float], Field(min_length=2, max_length=2)]


class CompareBars(Spec):
    type: Literal["compare_bars"] = "compare_bars"
    id: str
    title: str
    series: Annotated[list[Series], Field(min_length=2, max_length=2)]
    metrics: Annotated[list[Metric], Field(min_length=1)]


class Node(Spec):
    player: Text
    x: PitchX
    y: PitchY
    passes: Annotated[int, Field(ge=1)]


class Edge(Spec):
    source: Text
    target: Text
    passes: Annotated[int, Field(ge=1)]


class PassNetwork(Spec):
    type: Literal["pass_network"] = "pass_network"
    id: str
    title: str
    nodes: list[Node]
    edges: list[Edge]
    # The minute the drawn passes stop, as the query found it. None: the whole match.
    until_minute: Minute | None = None


class PassPair(Spec):
    """One row of the query: the passes from one player to one other player."""

    player: Text
    recipient: Text
    passes: Annotated[int, Field(ge=1)]
    x: PitchX
    y: PitchY
    until_minute: Minute | None = None


class TimelineRow(Spec):
    """One row of the query: one shot of the match."""

    match_id: int
    team: Text
    opponent: Text
    minute: Minute
    xg: ShotXg
    is_goal: bool
    player: str | None = None


class TimelineShot(Spec):
    minute: Minute
    xg: ShotXg
    # The xG of the team after this shot, rounded as the team's xg is.
    total: Annotated[float, Field(ge=0)]
    is_goal: bool
    player: str | None = None


class TimelineTeam(Spec):
    team: Text
    xg: Annotated[float, Field(ge=0)]
    # In minute order.
    shots: list[TimelineShot]


class XgTimeline(Spec):
    type: Literal["xg_timeline"] = "xg_timeline"
    id: str
    title: str
    # Arsenal, then the opponent.
    teams: Annotated[list[TimelineTeam], Field(min_length=2, max_length=2)]


Chart = ShotMap | CompareBars | PassNetwork | XgTimeline
ChartSpec = Annotated[Chart, Field(discriminator="type")]

Columns = Sequence[str]
Rows = Sequence[Sequence[JsonValue]]
Record = dict[str, JsonValue]


def to_records(
    chart_type: str, columns: Columns, rows: Rows, needed: tuple[str, ...]
) -> list[Record]:
    """Return each row as a mapping from column name to value."""
    names = list(columns)
    for name in names:
        if names.count(name) > 1:
            raise ChartRejected(f"The query has two columns named {name}.")
    missing = [name for name in needed if name not in columns]
    if missing:
        raise ChartRejected(
            f"A {chart_type} chart needs the columns {', '.join(needed)}."
            f" Missing: {', '.join(missing)}."
        )
    return [dict(zip(columns, row, strict=True)) for row in rows]


def parse_rows[Model: BaseModel](model: type[Model], records: list[Record]) -> list[Model]:
    parsed = []
    for number, record in enumerate(records, start=1):
        try:
            parsed.append(model.model_validate(record))
        except ValidationError as error:
            problem = error.errors()[0]
            raise ChartRejected(
                f"Row {number}, column {problem['loc'][0]}: {problem['msg']}."
            ) from None
    return parsed


def shot_map(columns: Columns, rows: Rows, title: str, chart_id: str) -> ShotMap:
    records = to_records(
        "shot_map", columns, rows, ("x", "y", "xg", "outcome", "minute", "opponent")
    )
    return ShotMap(id=chart_id, title=title, shots=parse_rows(Shot, records))


def is_chart_number(value: JsonValue) -> bool:
    """True for a number that a float can hold. A boolean is not a number here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # A whole number of any size can come from the database.
        return False


def compare_bars(columns: Columns, rows: Rows, title: str, chart_id: str) -> CompareBars:
    records = to_records("compare_bars", columns, rows, ("player", "season"))
    if len(records) != 2:
        raise ChartRejected(
            "A compare_bars chart needs exactly 2 rows, one for each player."
            f" The query returned {len(records)}."
        )
    series = parse_rows(Series, records)
    if series[0] == series[1]:
        raise ChartRejected(
            f"The two rows are the same player and season: {series[0].player}, {series[0].season}."
        )
    names = [name for name in columns if name not in ("player", "season")]
    if not names:
        raise ChartRejected(
            "A compare_bars chart needs one metric column or more next to player and season."
        )
    metrics = []
    for name in names:
        for record in records:
            value = record[name]
            if value is None:
                # The locked rule: a comparison across eras uses only shared metrics.
                raise ChartRejected(
                    f"The metric {name} is null for {record['player']}."
                    " A comparison uses only metrics that both players have."
                )
            if not is_chart_number(value):
                raise ChartRejected(
                    f"The metric {name} is not a number that a chart can hold"
                    f" for {record['player']}."
                )
        metrics.append(Metric(name=name, values=[record[name] for record in records]))
    return CompareBars(id=chart_id, title=title, series=series, metrics=metrics)


def pass_network(columns: Columns, rows: Rows, title: str, chart_id: str) -> PassNetwork:
    records = to_records("pass_network", columns, rows, ("player", "recipient", "passes", "x", "y"))
    pairs = parse_rows(PassPair, records)
    seen = set()
    by_passer: dict[str, list[PassPair]] = {}
    for number, pair in enumerate(pairs, start=1):
        if (pair.player, pair.recipient) in seen:
            raise ChartRejected(
                f"Row {number}: the pair {pair.player} to {pair.recipient} is in the rows"
                " two times. Group the passes by player and recipient."
            )
        seen.add((pair.player, pair.recipient))
        by_passer.setdefault(pair.player, []).append(pair)
        if pair.until_minute != pairs[0].until_minute:
            raise ChartRejected(
                f"Row {number}: until_minute is {pair.until_minute} here and"
                f" {pairs[0].until_minute} in row 1. The passes of one network stop at one minute."
            )

    nodes = []
    for player, made in sorted(by_passer.items()):
        total = sum(pair.passes for pair in made)
        try:
            # Each row holds the mean of its pair, so the weight is its pass count.
            x = round(sum(pair.passes * pair.x for pair in made) / total, 2)
            y = round(sum(pair.passes * pair.y for pair in made) / total, 2)
        except OverflowError:
            # A whole number of any size can come from the database.
            raise ChartRejected(f"The pass counts of {player} are too large for a chart.") from None
        nodes.append(Node(player=player, x=x, y=y, passes=total))
    # A recipient with no pass of their own has no position to draw an edge to.
    edges = [
        Edge(source=pair.player, target=pair.recipient, passes=pair.passes)
        for pair in pairs
        if pair.recipient in by_passer
    ]
    until_minute = pairs[0].until_minute if pairs else None
    return PassNetwork(
        id=chart_id, title=title, nodes=nodes, edges=edges, until_minute=until_minute
    )


def xg_timeline(columns: Columns, rows: Rows, title: str, chart_id: str) -> XgTimeline:
    records = to_records(
        "xg_timeline", columns, rows, ("match_id", "team", "opponent", "minute", "xg", "is_goal")
    )
    shots = parse_rows(TimelineRow, records)
    if not shots:
        raise ChartRejected("An xg_timeline chart needs one shot or more.")
    first = shots[0]
    if first.team == first.opponent:
        raise ChartRejected(f"The team and the opponent are both {first.team} in row 1.")
    # Each row names both teams, so a team with no shot still has its line.
    teams = {first.team, first.opponent}
    for number, shot in enumerate(shots, start=1):
        if shot.match_id != first.match_id:
            raise ChartRejected(
                f"Row {number}: match_id is {shot.match_id} here and {first.match_id} in row 1."
                " The shots of one timeline come from one match."
            )
        if {shot.team, shot.opponent} != teams:
            raise ChartRejected(
                f"Row {number}: the teams are {shot.team} and {shot.opponent} here and"
                f" {first.team} and {first.opponent} in row 1."
                " The shots of one timeline come from one match."
            )
    if ARSENAL not in teams:
        raise ChartRejected(
            f"The teams are {first.team} and {first.opponent}."
            " An xg_timeline shows an Arsenal match."
        )

    # sorted() is stable, so the shots of one minute keep the order of the rows.
    ordered = sorted(shots, key=lambda shot: shot.minute)
    lines = []
    for team in (ARSENAL, *(teams - {ARSENAL})):
        running = 0.0
        made = []
        for shot in ordered:
            if shot.team != team:
                continue
            # Rounded only for the spec: rounding the running sum would lose small shots.
            running += shot.xg
            made.append(
                TimelineShot(
                    minute=shot.minute,
                    xg=shot.xg,
                    total=round(running, 2),
                    is_goal=shot.is_goal,
                    player=shot.player,
                )
            )
        lines.append(TimelineTeam(team=team, xg=round(running, 2), shots=made))
    return XgTimeline(id=chart_id, title=title, teams=lines)


BUILDERS = {
    "shot_map": shot_map,
    "compare_bars": compare_bars,
    "pass_network": pass_network,
    "xg_timeline": xg_timeline,
}


def check_request(chart_type: str, title: str) -> str:
    """Return the title to use. Raise ChartRejected for a type or a title that cannot be."""
    if chart_type not in get_args(ChartType):
        raise ChartRejected(
            f"Unknown chart type {chart_type!r}. Known types: {', '.join(get_args(ChartType))}."
        )
    title = title.strip()
    if not 1 <= len(title) <= MAX_TITLE:
        raise ChartRejected(f"The title must have 1 to {MAX_TITLE} characters.")
    return title


def build(
    chart_type: str,
    columns: Columns,
    rows: Rows,
    title: str,
    chart_id: str,
) -> Chart:
    """Return the chart that the rows make. Raise ChartRejected if they make none."""
    title = check_request(chart_type, title)
    return BUILDERS[chart_type](columns, rows, title, chart_id)
