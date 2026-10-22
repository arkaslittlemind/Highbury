"""The data tools of the agent. Each one is a plain function.

A tool never raises for a bad input or a database failure. It returns a result
with error text, so that the agent can read the problem and try again.
"""

import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, JsonValue
from rapidfuzz import fuzz, utils

from analyst import charts, db
from analyst.settings import SettingsError
from analyst.sql_guard import AGENT_VIEWS, MAX_ROWS, SqlRejected, guard

STATEMENT_TIMEOUT_MS = 5000
TIMEOUT_TEXT = f"The query took longer than {STATEMENT_TIMEOUT_MS // 1000} seconds and was stopped."
TOO_MANY_ROWS_TEXT = (
    f"The query reached the limit of {MAX_ROWS} rows. A chart needs every row, so narrow the query."
)
NO_ROWS_TEXT = "The query returned no rows, so there is no chart."

# rapidfuzz scores from 0 to 100. A name below the cutoff is not a match. The best
# player must lead the next one by FUZZY_LEAD to be the one answer. On the real
# names, a shared short word such as "van" scores 85.5 and a misspelled name 88.
FUZZY_CUTOFF = 86
FUZZY_LEAD = 5
MAX_MATCHES = 5

READ_ERRORS = (db.DatabaseUnavailable, db.QueryTimeout, db.QueryFailed, SettingsError)

Method = Literal["exact", "fuzzy"]


class SqlResult(BaseModel):
    call_id: str
    ok: bool
    # The statement that ran. None when the guard rejected the input.
    sql: str | None = None
    columns: list[str] = []
    rows: list[list[JsonValue]] = []
    row_count: int = 0
    # True when the row limit of the guard cut the result, so more rows can exist.
    limit_reached: bool = False
    error: str | None = None


class CatalogRow(BaseModel):
    season: str
    metric: str
    available: bool
    source: str | None
    notes: str | None


class CatalogResult(BaseModel):
    rows: list[CatalogRow] = []
    error: str | None = None


class ColumnInfo(BaseModel):
    name: str
    type: str
    description: str


class ViewInfo(BaseModel):
    name: str
    description: str
    columns: list[ColumnInfo]


class SchemaResult(BaseModel):
    views: list[ViewInfo] = []
    error: str | None = None


class PlayerMatch(BaseModel):
    # players.name: the value of the player column in the views.
    player: str
    seasons: list[str]
    teams: list[str]
    # The name or alias that the query matched.
    matched_on: str
    method: Method
    score: float


class ResolveResult(BaseModel):
    query: str
    # error: the lookup did not run. It does not mean that there is no such player.
    status: Literal["found", "ambiguous", "not_found", "error"]
    matches: list[PlayerMatch] = []
    error: str | None = None


class ChartResult(BaseModel):
    ok: bool
    chart: charts.ChartSpec | None = None
    # The id of the query that gave the rows. None when no query ran.
    call_id: str | None = None
    sql: str | None = None
    row_count: int = 0
    error: str | None = None


def error_text(error: Exception) -> str:
    return TIMEOUT_TEXT if isinstance(error, db.QueryTimeout) else str(error)


def json_safe(value: Any) -> JsonValue:
    """Return a value that JSON can hold and that the claim check can compare."""
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            return str(value)
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, date | datetime | time):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, bytes | memoryview):
        # The text form that PostgreSQL uses for bytea.
        return "\\x" + bytes(value).hex()
    return str(value)


def run_sql(sql: str) -> SqlResult:
    """Run one read-only SELECT on the agent's views and return its rows."""
    # Later features cite this id in a claim, so a failed call has one too.
    call_id = f"q_{uuid.uuid4().hex[:8]}"
    try:
        guarded = guard(sql)
    except SqlRejected as error:
        return SqlResult(call_id=call_id, ok=False, error=str(error))
    try:
        result = db.read(guarded.sql, STATEMENT_TIMEOUT_MS)
    except READ_ERRORS as error:
        return SqlResult(call_id=call_id, ok=False, sql=guarded.sql, error=error_text(error))

    rows = [[json_safe(value) for value in row] for row in result.rows]
    return SqlResult(
        call_id=call_id,
        ok=True,
        sql=guarded.sql,
        columns=result.columns,
        rows=rows,
        row_count=len(rows),
        limit_reached=guarded.capped and len(rows) == MAX_ROWS,
    )


def get_data_catalog(season: str | None = None) -> CatalogResult:
    """Return what data each season has. Give a season label to get one season."""
    try:
        result = db.read(
            "SELECT s.label, c.metric, c.available, c.source, c.notes"
            " FROM seasons s LEFT JOIN data_catalog c ON c.season_id = s.id"
            # The C collation gives one order on every server.
            ' ORDER BY s.label COLLATE "C", c.metric COLLATE "C"',
            STATEMENT_TIMEOUT_MS,
        )
    except READ_ERRORS as error:
        return CatalogResult(error=error_text(error))

    rows = [
        CatalogRow(season=label, metric=metric, available=available, source=source, notes=notes)
        for label, metric, available, source, notes in result.rows
        if metric is not None
    ]
    if season is None:
        return CatalogResult(rows=rows)

    # People and models also write the label with a slash or with an en dash.
    wanted = season.strip().replace("/", "-").replace("\N{EN DASH}", "-")
    known = sorted({row[0] for row in result.rows})
    if wanted not in known:
        return CatalogResult(
            error=f"Unknown season {season!r}. Known seasons: {', '.join(known) or 'none'}."
        )
    return CatalogResult(rows=[row for row in rows if row.season == wanted])


def get_schema() -> SchemaResult:
    """Return the views that run_sql can read, with the comment of each column."""
    views = list(AGENT_VIEWS)
    try:
        result = db.read(
            "SELECT c.relname, obj_description(c.oid, 'pg_class'), a.attname,"
            " format_type(a.atttypid, a.atttypmod), col_description(c.oid, a.attnum)"
            " FROM pg_class c"
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            " JOIN pg_attribute a ON a.attrelid = c.oid"
            " WHERE n.nspname = 'public' AND c.relname = ANY(%s)"
            " AND a.attnum > 0 AND NOT a.attisdropped"
            " ORDER BY array_position(%s, c.relname::text), a.attnum",
            STATEMENT_TIMEOUT_MS,
            [views, views],
        )
    except READ_ERRORS as error:
        return SchemaResult(error=error_text(error))

    found: dict[str, ViewInfo] = {}
    for view, view_comment, column, column_type, column_comment in result.rows:
        info = found.setdefault(
            view, ViewInfo(name=view, description=view_comment or "", columns=[])
        )
        info.columns.append(
            ColumnInfo(name=column, type=column_type, description=column_comment or "")
        )
    return SchemaResult(views=list(found.values()))


def name_key(text: str) -> str:
    """Return the form in which two spellings are one name."""
    return " ".join(text.split()).casefold()


@dataclass(frozen=True)
class Candidate:
    player_id: int
    player: str
    matched_on: str
    score: float


def rank_players(query: str, names: list[tuple[int, str, str]]) -> tuple[Method, list[Candidate]]:
    """Return the players that the query can mean, best first.

    names holds (player id, canonical name, a name or alias of that player). An
    exact match on a name or an alias wins. Only if there is none, the closest
    names are the matches.
    """
    best: dict[int, Candidate] = {}
    method: Method = "exact"
    for player_id, player, text in names:
        if name_key(text) == name_key(query) and player_id not in best:
            best[player_id] = Candidate(player_id, player, text, 100.0)
    if not best:
        method = "fuzzy"
        for player_id, player, text in names:
            score = fuzz.WRatio(query, text, processor=utils.default_process)
            if score >= FUZZY_CUTOFF and (player_id not in best or score > best[player_id].score):
                best[player_id] = Candidate(player_id, player, text, round(score, 1))
    # The name and the id make the order of equal scores stable.
    ranked = sorted(best.values(), key=lambda c: (-c.score, c.player, c.player_id))
    return method, ranked[:MAX_MATCHES]


def resolve_player(name: str) -> ResolveResult:
    """Find the player that a name or a nickname means.

    Use the player value of a match in SQL. The seasons and the teams of a match
    tell two players of one name apart.
    """
    query = " ".join(name.split())
    if not query:
        return ResolveResult(query=name, status="not_found", error="The player name is empty.")
    try:
        names = db.read(
            "SELECT p.id, p.name, n.text FROM players p JOIN ("
            " SELECT id AS player_id, name AS text FROM players"
            " UNION SELECT player_id, source_name FROM player_aliases"
            ") n ON n.player_id = p.id ORDER BY p.id, n.text",
            STATEMENT_TIMEOUT_MS,
        ).rows
        method, ranked = rank_players(query, names)
        if not ranked:
            return ResolveResult(query=query, status="not_found")
        appearances = db.read(
            "SELECT DISTINCT pms.player_id, s.label, t.name"
            " FROM player_match_stats pms"
            " JOIN matches m ON m.id = pms.match_id"
            " JOIN seasons s ON s.id = m.season_id"
            " JOIN teams t ON t.id = pms.team_id"
            " WHERE pms.player_id = ANY(%s)",
            STATEMENT_TIMEOUT_MS,
            [[candidate.player_id for candidate in ranked]],
        ).rows
    except READ_ERRORS as error:
        return ResolveResult(query=query, status="error", error=error_text(error))

    matches = [
        PlayerMatch(
            player=c.player,
            seasons=sorted(
                {label for player_id, label, _ in appearances if player_id == c.player_id}
            ),
            teams=sorted({team for player_id, _, team in appearances if player_id == c.player_id}),
            matched_on=c.matched_on,
            method=method,
            score=c.score,
        )
        for c in ranked
    ]
    one_answer = len(matches) == 1 or (
        method == "fuzzy" and matches[0].score - matches[1].score >= FUZZY_LEAD
    )
    return ResolveResult(
        query=query, status="found" if one_answer else "ambiguous", matches=matches
    )


def build_chart(chart_type: charts.ChartType, sql: str, title: str) -> ChartResult:
    """Build a chart from the rows of one SELECT. The chart holds its data.

    The SQL has the rules of run_sql. Each chart type needs its columns:
    shot_map: one row for each shot, with x, y, xg, outcome, minute, opponent. It
    also takes player, season, match_date. SELECT * FROM v_shots works.
    compare_bars: exactly two rows, one for each player, with player and season.
    Each other column is a metric and must be a number for both players.
    pass_network: one row for each pair of passer and recipient, with player,
    recipient, passes (the count), x and y (the mean start position). Group
    v_passes by player and recipient. An optional until_minute column, the same on
    every row, is the minute the passes stop; leave it out for the whole match.
    """
    try:
        title = charts.check_request(chart_type, title)
    except charts.ChartRejected as error:
        return ChartResult(ok=False, error=str(error))

    # The chart rows come through run_sql, so the guard, the row limit and the
    # timeout hold for them too.
    result = run_sql(sql)
    query = {"call_id": result.call_id, "sql": result.sql, "row_count": result.row_count}
    if not result.ok:
        return ChartResult(ok=False, error=result.error, **query)
    if result.limit_reached:
        # A chart of the first rows only would show wrong totals.
        return ChartResult(ok=False, error=TOO_MANY_ROWS_TEXT, **query)
    if not result.rows:
        return ChartResult(ok=False, error=NO_ROWS_TEXT, **query)
    try:
        chart = charts.build(
            chart_type, result.columns, result.rows, title, f"c_{uuid.uuid4().hex[:8]}"
        )
    except charts.ChartRejected as error:
        return ChartResult(ok=False, error=str(error), **query)
    return ChartResult(ok=True, chart=chart, **query)
