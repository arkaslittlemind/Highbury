"""Verified match reports: one short report on each of Arsenal's 76 league matches.

Run it from the repository root, then commit the file:
uv run --env-file .env python -m analyst.match_reports

Each question costs money, so the run happens once, offline, and the pages of the web
app read the committed file: a visitor's view calls no model. The agent writes the
text and the verifier checks it, as for a visitor's question. A report is kept only
when every claim passed and the summary has no unbacked number. The command asks
again a fixed number of times, then leaves the match out and lists it. The charts
come from fixed queries, as the landing tiles do, so the agent spends its tool calls
on the numbers that it must back.
"""

import argparse
import json
import re
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ValidationError

from analyst import agent, charts, evals, landing_data
from analyst.agent import AgentError, Turn, Usage
from analyst.settings import SettingsError, model_name

OUTPUT = Path("apps/web/src/lib/match-reports.json")
MODELS_FILE = evals.EVALS_DIR / "models.yaml"
# The first ask and two more. A report that fails three times is left out and listed.
MAX_ATTEMPTS = 3
ARSENAL = "Arsenal"
# Pass events exist only for this season.
PASS_SEASON = "2003-04"

MATCHES_SQL = (
    "SELECT match_id, season, match_date, home_team, away_team, home_goals, away_goals"
    f" FROM v_matches WHERE '{ARSENAL}' IN (home_team, away_team) ORDER BY season, match_date"
)

Reader = landing_data.Reader
# Asks one question on a new conversation. Raises AgentError when the turn gives no answer.
Ask = Callable[[str], Turn]


class MatchReportError(Exception):
    """The run stopped. The text names what to fix."""


class OutOfCredit(MatchReportError):
    """The provider wants payment. Every later question would fail the same way."""


class MatchInfo(BaseModel):
    # The identity of the database. It changes when the database is built again, so
    # the file does not hold it: the slug is the stable key.
    match_id: int
    season: str
    match_date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int

    @property
    def arsenal_home(self) -> bool:
        return self.home_team == ARSENAL

    @property
    def opponent(self) -> str:
        return self.away_team if self.arsenal_home else self.home_team

    @property
    def slug(self) -> str:
        return slug_of(self.match_date, self.opponent)

    def fields(self) -> dict:
        """The match fields of a report and of a left-out entry."""
        return {"slug": self.slug, **self.model_dump(exclude={"match_id"})}


def slug_of(match_date: str, opponent: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", opponent.lower()).strip("-")
    return f"{match_date}-{name}"


def load_matches(read: Reader) -> list[MatchInfo]:
    matches = [MatchInfo(**row) for row in landing_data.records_of(read, MATCHES_SQL)]
    seen: set[str] = set()
    for match in matches:
        if match.slug in seen:
            raise MatchReportError(f"Two matches have the slug {match.slug}.")
        seen.add(match.slug)
    return matches


def timeline_sql(match_id: int) -> str:
    return (
        "SELECT match_id, team, opponent, minute, xg, is_goal, player FROM v_shots"
        f" WHERE match_id = {match_id} ORDER BY minute"
    )


def network_sql(match_id: int) -> str:
    # The rule of the pass network example of the prompt: Arsenal's completed passes
    # before their first substitution. ALL over no rows is true, so a match with no
    # change keeps every pass.
    changes = f"FROM v_substitutions WHERE team = '{ARSENAL}' AND match_id = {match_id}"
    return (
        "SELECT player, recipient, count(*) AS passes, round(avg(x)::numeric, 2) AS x,"
        " round(avg(y)::numeric, 2) AS y,"
        f" (SELECT minute {changes} ORDER BY period, minute, second LIMIT 1) AS until_minute"
        f" FROM v_passes WHERE team = '{ARSENAL}' AND outcome IS NULL"
        f" AND recipient IS NOT NULL AND match_id = {match_id}"
        f" AND (period, minute, second) < ALL (SELECT period, minute, second {changes})"
        " GROUP BY player, recipient ORDER BY player, recipient"
    )


def score_line(match: MatchInfo) -> str:
    return (
        f"{match.home_team} {match.home_goals}-{match.away_goals} {match.away_team}, {match.season}"
    )


def chart(match: MatchInfo, chart_type: str, sql: str, title: str, suffix: str, read: Reader):
    columns, rows = read(sql)
    try:
        built = charts.build(chart_type, columns, rows, title, f"{match.slug}-{suffix}")
    except charts.ChartRejected as error:
        raise MatchReportError(f"{match.slug}: the {chart_type} chart failed: {error}") from None
    return built.model_dump(mode="json")


def match_charts(match: MatchInfo, read: Reader) -> list[dict]:
    timeline = timeline_sql(match.match_id)
    built = [chart(match, "xg_timeline", timeline, score_line(match), "xg", read)]
    if match.season == PASS_SEASON:
        title = f"Arsenal's pass network v {match.opponent}, {match.season}"
        built.append(
            chart(match, "pass_network", network_sql(match.match_id), title, "network", read)
        )
    return built


def report_question(match: MatchInfo) -> str:
    day = date.fromisoformat(match.match_date)
    where = "at home to" if match.arsenal_home else "away at"
    topics = "the result, the scorers, and how the xG went"
    if match.season == PASS_SEASON:
        topics += ", and Arsenal's main passing links"
    return (
        f"Write a short report on Arsenal's league match {where} {match.opponent} on"
        f" {day.day} {day:%B %Y} ({match.season}): {topics}. Back every number with a"
        " claim. Do not draw a chart."
    )


def failure(turn: Turn) -> str | None:
    """Why a turn cannot be published, or None when it can."""
    if turn.answer.status != "answered":
        return f"status {turn.answer.status}"
    verification = turn.verification
    if verification.removed:
        removed = "; ".join(f"{item.reason} ({item.claim.text})" for item in verification.removed)
        return f"removed claims: {removed}"
    if verification.unbacked_numbers:
        return f"unbacked numbers: {', '.join(verification.unbacked_numbers)}"
    if not turn.answer.claims:
        return "no claim"
    return None


def ask_match(match: MatchInfo, ask: Ask, usage: Usage) -> tuple[Turn | None, list[str]]:
    """The first turn that can be published, and the reasons of the attempts that failed."""
    question = report_question(match)
    reasons: list[str] = []
    for _ in range(MAX_ATTEMPTS):
        try:
            turn = ask(question)
        except AgentError as error:
            evals.add_usage(usage, error.usage)
            if agent.out_of_credit(error):
                raise OutOfCredit(
                    f"The provider wants payment. The run stopped at {match.slug};"
                    " the file keeps the matches before it."
                ) from error
            reasons.append(f"error: {error}")
            continue
        evals.add_usage(usage, turn.usage)
        reason = failure(turn)
        if reason is None:
            return turn, reasons
        reasons.append(reason)
    return None, reasons


def report_of(match: MatchInfo, turn: Turn, attempts: int, built: list[dict]) -> dict:
    statements = {
        record.result.get("call_id"): record.result.get("sql")
        for record in turn.records
        if record.name == "run_sql"
    }
    return {
        **match.fields(),
        "summary": turn.answer.summary,
        "caveats": turn.answer.caveats,
        # The SQL of the cited query, so a reader can run it again. The verifier
        # found the value in its rows, so the statement is there.
        "claims": [
            {
                "text": claim.text,
                "value": claim.value,
                "unit": claim.unit,
                "sql": statements[claim.tool_call_id],
            }
            for claim in turn.answer.claims
        ],
        "verification": turn.verification.model_dump(mode="json"),
        "attempts": attempts,
        "charts": built,
    }


def new_file(model: str) -> dict:
    return {
        "generated_at": None,
        "model": model,
        "max_attempts": MAX_ATTEMPTS,
        "reports": [],
        "left_out": [],
    }


def order(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda entry: (entry["season"], entry["match_date"]))


def to_json(data: dict) -> str:
    """The same data gives the same bytes. One line for each report keeps a diff readable."""

    def compact(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def block(entries: list[dict]) -> str:
        if not entries:
            return "[]"
        return "[\n    " + ",\n    ".join(compact(entry) for entry in entries) + "\n  ]"

    head = "".join(
        f"  {compact(key)}: {compact(data[key])},\n"
        for key in ("generated_at", "model", "max_attempts")
    )
    return (
        f"{{\n{head}"
        f'  "reports": {block(data["reports"])},\n'
        f'  "left_out": {block(data["left_out"])}\n}}\n'
    )


def read_file(path: Path, model: str) -> dict:
    if not path.exists():
        return new_file(model)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = set(new_file(model))
        if not isinstance(data, dict) or set(data) != known:
            raise ValueError
    except ValueError:
        raise MatchReportError(f"{path} is not a match report file.") from None
    if data["model"] != model and (data["reports"] or data["left_out"]):
        # One file holds the reports of one model, so it says which model wrote them.
        raise MatchReportError(
            f"{path} was made with {data['model']}, but ANALYST_MODEL is {model}."
            " Use the same model, or move the file away to start again."
        )
    data["model"] = model
    return data


def production_ask() -> Ask:
    graph = agent.build_agent()

    def ask(question: str) -> Turn:
        # A new thread for each attempt: a retry must not read the failed answer.
        return agent.ask(graph, question, uuid.uuid4().hex)

    return ask


def today() -> str:
    return date.today().isoformat()


@dataclass
class Deps:
    """What main reaches outside the process. A test gives its own."""

    read: Reader = landing_data.read_with_tools
    model_name: Callable[[], str] = model_name
    # Called once, after the arguments and the file pass their checks.
    build_ask: Callable[[], Ask] = production_ask
    today: Callable[[], str] = today
    sleep: Callable[[float], None] = time.sleep
    out: Callable[[str], None] = print
    output: Path = OUTPUT
    models_file: Path = MODELS_FILE


def generate(
    todo: list[MatchInfo], data: dict, ask: Ask, deps: Deps, pause: float, usage: Usage
) -> None:
    # Every chart is built before the first paid question, so a chart that fails
    # costs nothing.
    built = {match.slug: match_charts(match, deps.read) for match in todo}
    for number, match in enumerate(todo):
        if number and pause:
            deps.sleep(pause)
        turn, reasons = ask_match(match, ask, usage)
        reports = [entry for entry in data["reports"] if entry["slug"] != match.slug]
        left_out = [entry for entry in data["left_out"] if entry["slug"] != match.slug]
        if turn is None:
            left_out.append({**match.fields(), "reasons": reasons})
            deps.out(f"{match.slug} left out after {MAX_ATTEMPTS} attempts")
        else:
            attempts = len(reasons) + 1
            reports.append(report_of(match, turn, attempts, built[match.slug]))
            deps.out(f"{match.slug} kept on attempt {attempts}")
        data.update(reports=order(reports), left_out=order(left_out), generated_at=deps.today())
        # Written after each match, so a stopped run keeps what it paid for.
        deps.output.write_text(to_json(data), encoding="utf-8", newline="\n")


def cost_text(model: str, usage: Usage, models_file: Path) -> str:
    try:
        entries = evals.load_models(models_file).models
    except evals.EvalError:
        entries = []
    entry = next((entry for entry in entries if entry.id == model), None)
    if entry is None:
        return "cost unknown"
    return f"${evals.cost(usage, entry):.4f}"


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="match_reports", description="Write a verified report on each league match."
    )
    parser.add_argument(
        "--only", action="append", help="a match slug, for example 2004-04-09-liverpool"
    )
    parser.add_argument("--pause", type=float, default=0, help="seconds between matches")
    parser.add_argument("--limit", type=int, help="ask at most this many matches")
    args = parser.parse_args(argv)
    if args.pause < 0:
        parser.error("--pause must be 0 or more")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be 1 or more")
    return args


def main(argv: Sequence[str] | None = None, *, deps: Deps | None = None) -> int:
    args = parse(argv)
    deps = deps or Deps()
    usage = Usage()
    status = 0
    data: dict | None = None
    try:
        model = deps.model_name()
        matches = load_matches(deps.read)
        data = read_file(deps.output, model)
        if args.only:
            unknown = set(args.only) - {match.slug for match in matches}
            if unknown:
                raise MatchReportError(f"Unknown match: {', '.join(sorted(unknown))}.")
            todo = [match for match in matches if match.slug in args.only]
        else:
            # Resume: a kept report is not asked again; a left-out match is, but after
            # the matches never asked, so a batch does not keep paying for a match that
            # keeps failing before it reaches new ones.
            kept = {entry["slug"] for entry in data["reports"]}
            failed = {entry["slug"] for entry in data["left_out"]}
            new = [match for match in matches if match.slug not in kept | failed]
            todo = new + [match for match in matches if match.slug in failed]
        # The key of the run is also the key of the site: a batch spends only part of
        # the credit, and the next run goes on from the first match never asked;
        # left-out matches come last.
        todo = todo[: args.limit]
        if todo:
            generate(todo, data, deps.build_ask(), deps, args.pause, usage)
    except (MatchReportError, AgentError, SettingsError, ValidationError) as error:
        deps.out(f"Match reports stopped: {error}")
        status = 1
    # After a stop the counts still say what the paid calls bought.
    if data is not None and (status == 0 or usage.model_calls):
        left = [entry["slug"] for entry in data["left_out"]]
        waiting = len(matches) - len(data["reports"]) - len(left)
        deps.out(
            f"{len(data['reports'])} kept, {len(left)} left out"
            + (f": {', '.join(left)}" if left else "")
        )
        if waiting:
            deps.out(f"{waiting} matches not asked yet")
        cost = cost_text(data["model"], usage, deps.models_file)
        deps.out(
            f"{usage.model_calls} model calls, {usage.input_tokens} input and"
            f" {usage.output_tokens} output tokens, {cost}"
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
