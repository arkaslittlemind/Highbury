"""The data of the landing page: the chart gallery, the season records, the numbers of
the capability cards, and the eval proof band.

Run it from the repository root after a data load or an eval run, and commit the file:
uv run --env-file .env python -m analyst.landing_data

The page shows real rows, but it reads no database: a visitor sees the charts before
any question, and the page must not wait for the API. So this script makes one JSON
file with the same chart builders, the same SQL guard, and the same read-only role as
the agent, and the web app imports it.
"""

import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import JsonValue

from analyst import charts, evals, prompt, tools

OUTPUT = Path("apps/web/src/lib/landing-data.json")
EVALS_DIR = evals.EVALS_DIR

Columns = list[str]
Rows = list[list[JsonValue]]
# Runs one SELECT and gives its columns and rows. The script uses tools.run_sql; a test
# gives fixed rows.
Reader = Callable[[str], tuple[Columns, Rows]]


class LandingDataError(Exception):
    """A query or an input file does not give the data. The text says why."""


@dataclass(frozen=True)
class Tile:
    # The id of the golden question that the tile shows. Its Try link asks it.
    golden_id: str
    chart_type: charts.ChartType
    title: str
    label: str
    season: str
    sql: str


TOTTENHAM_AWAY = (
    "(SELECT match_id FROM v_matches WHERE season = '2003-04'"
    " AND home_team = 'Tottenham Hotspur' AND away_team = 'Arsenal')"
)
HENRY_V_SAKA = (
    "FROM v_player_season WHERE (player = 'Thierry Henry' AND season = '2003-04')"
    " OR (player = 'Bukayo Saka' AND season = '2025-26')"
)

# The queries are the examples of the agent's prompt where one exists, so a tile is the
# chart that the agent learns to draw for its question.
TILES = (
    Tile(
        "q01",
        "shot_map",
        "Thierry Henry's shots, 2003-04",
        "Henry's shots",
        "Both seasons",
        "SELECT x, y, xg, outcome, minute, opponent, player, season, match_date FROM v_shots"
        " WHERE player = 'Thierry Henry' AND season = '2003-04' ORDER BY match_date, minute",
    ),
    Tile(
        "q26",
        "heatmap",
        "Thierry Henry's touches, 2003-04",
        "Henry's touches",
        "2003-04",
        "SELECT least(floor(x / 10), 11)::int AS zone_x, least(floor(y / 10), 7)::int AS zone_y,"
        f" count(*) AS touches, player, season {prompt.HENRY_TOUCHES}"
        " GROUP BY zone_x, zone_y, player, season ORDER BY zone_x, zone_y",
    ),
    Tile(
        "q25",
        "pass_map",
        "Patrick Vieira's long passes, 2003-04",
        "Vieira's long passes",
        "2003-04",
        "SELECT x, y, end_x, end_y, outcome, minute, opponent, player, recipient, season,"
        f" match_date {prompt.VIEIRA_LONG_PASSES} ORDER BY match_date, period, minute, second",
    ),
    Tile(
        "q10",
        "pass_network",
        "Arsenal's pass network v Liverpool at home, 2003-04",
        "Network v Liverpool",
        "2003-04",
        "SELECT player, recipient, count(*) AS passes, round(avg(x)::numeric, 2) AS x,"
        f" round(avg(y)::numeric, 2) AS y, {prompt.UNTIL_MINUTE} {prompt.LIVERPOOL_HOME_PASSES}"
        " GROUP BY player, recipient ORDER BY player, recipient",
    ),
    Tile(
        "q16",
        "xg_timeline",
        "Tottenham Hotspur v Arsenal, 2003-04",
        "Spurs 2-2 Arsenal",
        "Both seasons",
        "SELECT match_id, team, opponent, minute, xg, is_goal, player FROM v_shots"
        f" WHERE match_id = {TOTTENHAM_AWAY} ORDER BY minute",
    ),
    Tile(
        "q18",
        "points_pace",
        "Arsenal's points pace, 2003-04 and 2025-26",
        "Then vs now",
        "Both seasons",
        "SELECT team, season, match_date, opponent, goals_for, goals_against"
        f" FROM {prompt.TEAM_MATCHES} WHERE {prompt.PACE_LINES} ORDER BY season, match_date",
    ),
    Tile(
        "q02",
        "compare_bars",
        "Thierry Henry 2003-04 v Bukayo Saka 2025-26",
        "Henry vs Saka",
        "Both seasons",
        "SELECT player, season, goals, round((goals * 90.0 / NULLIF(minutes, 0))::numeric, 2)"
        " AS goals_per_90, round((xg * 90.0 / NULLIF(minutes, 0))::numeric, 2) AS xg_per_90"
        f" {HENRY_V_SAKA} ORDER BY season",
    ),
)

RECORDS_SQL = (
    "SELECT season, won, drawn, lost FROM v_league_table WHERE team = 'Arsenal' ORDER BY season"
)
# The numbers of capability card 4: a check of Saka's minutes and goals per 90, and of
# Henry's goals per 90.
PLAYER_SQL = (
    "SELECT player, season, minutes, round((goals * 90.0 / NULLIF(minutes, 0))::numeric, 2)"
    f" AS goals_per_90 {HENRY_V_SAKA} ORDER BY season"
)


def read_with_tools(sql: str) -> tuple[Columns, Rows]:
    """Run one query as the agent does: the SQL guard, the row cap, and analyst_ro."""
    result = tools.run_sql(sql)
    if not result.ok:
        raise LandingDataError(f"The query failed: {result.error}\n{sql}")
    if result.limit_reached:
        raise LandingDataError(
            f"The query reached the row limit, so a chart would be wrong.\n{sql}"
        )
    if not result.rows:
        raise LandingDataError(f"The query returned no rows.\n{sql}")
    return list(result.columns), [list(row) for row in result.rows]


# A tile is a picture about 270 px wide, so it keeps only what it draws: the title
# names the player and the season once, and a tenth of a pitch unit is less than a
# pixel. The answer charts keep every field.
SLIM_NULL = {"shot_map": ("player", "season", "match_date")}
SLIM_DROP = {"pass_map": ("recipient", "season", "match_date")}
SLIM_ROWS = {"shot_map": "shots", "pass_map": "passes"}
COORDINATES = ("x", "y", "end_x", "end_y")


def slim(chart: dict) -> dict:
    """A chart spec for a tile: the same rows, with no field that the tile does not draw."""
    key = SLIM_ROWS.get(chart["type"])
    if key is None:
        return chart
    rows = []
    for row in chart[key]:
        row = dict(row)
        for name in SLIM_NULL.get(chart["type"], ()):
            row[name] = None
        for name in SLIM_DROP.get(chart["type"], ()):
            row.pop(name, None)
        for name in COORDINATES:
            if name in row:
                row[name] = round(row[name], 1)
        if "xg" in row:
            # The radius of a mark comes from xG: a thousandth is far below a pixel.
            row["xg"] = round(row["xg"], 3)
        rows.append(row)
    return {**chart, key: rows}


def records_of(read: Reader, sql: str) -> list[dict[str, JsonValue]]:
    columns, rows = read(sql)
    return [dict(zip(columns, row, strict=True)) for row in rows]


def tile_data(tile: Tile, golden: dict[str, evals.GoldenItem], read: Reader) -> dict:
    item = golden.get(tile.golden_id)
    if item is None:
        raise LandingDataError(f"The golden question {tile.golden_id} does not exist.")
    if item.chart != tile.chart_type:
        raise LandingDataError(
            f"The golden question {tile.golden_id} has the chart {item.chart},"
            f" but its tile draws {tile.chart_type}."
        )
    columns, rows = read(tile.sql)
    try:
        chart = charts.build(tile.chart_type, columns, rows, tile.title, f"tile_{tile.golden_id}")
    except charts.ChartRejected as error:
        raise LandingDataError(f"The tile {tile.golden_id} has no chart: {error}") from None
    return {
        "id": tile.golden_id,
        "question": item.question,
        "label": tile.label,
        "season": tile.season,
        "chart": slim(chart.model_dump(mode="json")),
    }


def season_records(read: Reader) -> dict[str, dict[str, JsonValue]]:
    return {
        str(row["season"]): {"won": row["won"], "drawn": row["drawn"], "lost": row["lost"]}
        for row in records_of(read, RECORDS_SQL)
    }


def capability_numbers(read: Reader) -> dict[str, JsonValue]:
    players = {str(row["player"]): row for row in records_of(read, PLAYER_SQL)}
    try:
        henry, saka = players["Thierry Henry"], players["Bukayo Saka"]
    except KeyError as error:
        raise LandingDataError(f"No season row for {error.args[0]}.") from None
    return {
        "sakaMinutes": saka["minutes"],
        "sakaGoalsPer90": saka["goals_per_90"],
        "henryGoalsPer90": henry["goals_per_90"],
    }


def proof_numbers(evals_dir: Path, items: Sequence[evals.GoldenItem]) -> dict[str, JsonValue]:
    """The eval numbers of the production model, as results.md shows them."""
    model_file = evals.load_models(evals_dir / "models.yaml")
    if model_file.decision is None:
        raise LandingDataError("models.yaml has no decision, so no model is in production.")
    model = model_file.decision.model
    runs = [run for run in evals.read_runs(evals_dir / "runs") if run.model.id == model]
    if not runs:
        raise LandingDataError(f"No eval run of {model} is in {evals_dir / 'runs'}.")
    # The page shows whole questions, so it takes the newest run and not a mean of runs.
    run = max(runs, key=lambda run: run.started_at)
    summary = evals.summarize(run.results, list(items))
    verified = evals.percent(summary.verified_rate)
    return {
        "model": model.split(":", 1)[-1],
        "runDate": run.started_at[:10],
        "correct": summary.correct,
        "correctTotal": summary.questions,
        "verifiedRate": None if verified is None else round(verified),
        "chartMatches": summary.chart_match,
        "chartTotal": summary.chart_items,
        "refusals": summary.refusals_correct,
        "refusalTotal": summary.refusal_items,
    }


def build(read: Reader, evals_dir: Path = EVALS_DIR) -> dict:
    items = evals.load_golden(evals_dir / "golden.yaml")
    golden = {item.id: item for item in items}
    return {
        "tiles": [tile_data(tile, golden, read) for tile in TILES],
        "records": season_records(read),
        "capabilities": capability_numbers(read),
        "proof": proof_numbers(evals_dir, items),
    }


def to_json(data: dict) -> str:
    # Insertion order and no spaces, so the same data gives the same bytes and the page
    # bundle stays small. One line for each tile keeps a diff readable.
    def compact(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    tiles = ",\n    ".join(compact(tile) for tile in data["tiles"])
    rest = "".join(
        f",\n  {compact(key)}: {compact(value)}" for key, value in data.items() if key != "tiles"
    )
    return f'{{\n  "tiles": [\n    {tiles}\n  ]{rest}\n}}\n'


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    try:
        data = build(read_with_tools)
    except (LandingDataError, evals.EvalError) as error:
        print(error, file=sys.stderr)
        return 1
    OUTPUT.write_text(to_json(data), encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes, {len(data['tiles'])} tiles).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
