"""Evals: ask the golden questions through the agent, score each answer, and write a table.

The questions and the models are files in evals/ at the root of the repository. The
expected values come from hand-written SQL that runs as analyst_ro, never from a model.
"""

import argparse
import re
import statistics
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from analyst import agent, sql_guard, tools
from analyst.agent import AgentError, Turn, Usage
from analyst.charts import ChartType
from analyst.settings import SettingsError
from analyst.verifier import cell_matches

Status = Literal["answered", "unavailable", "out_of_scope"]
REFUSALS = ("unavailable", "out_of_scope")
EVALS_DIR = Path("evals")
# A slow model call is a failed question, not a run that waits for ever. The preview
# models of a provider can take more than a minute or give a 504 when they are busy.
MODEL_TIMEOUT_SECONDS = 120
MODEL_RETRIES = 1


class EvalError(Exception):
    """A file of the evals or a golden query is not usable. The text says why."""


class GoldenItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^q\d{2}$")
    question: str = Field(min_length=1)
    status: Status
    chart: ChartType | None = None
    sql: str | None = None
    # The queries of other fair readings of the question. A correct answer claims
    # every value of one reading.
    also_sql: list[str] = []
    # Questions asked first in the same conversation. They are not scored.
    before: list[str] = []
    note: str | None = None

    @model_validator(mode="after")
    def sql_only_for_answers(self) -> "GoldenItem":
        if (self.status == "answered") != (self.sql is not None):
            raise ValueError("an answered item needs sql, and only an answered item has it")
        if self.also_sql and self.status != "answered":
            raise ValueError("only an answered item has also_sql")
        return self

    def queries(self) -> list[str]:
        return [self.sql, *self.also_sql] if self.sql else []


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The init_chat_model name, the same form as ANALYST_MODEL.
    id: str = Field(min_length=1)
    input_usd_per_mtok: float = Field(ge=0)
    output_usd_per_mtok: float = Field(ge=0)
    price_source: str
    price_date: str
    price_note: str | None = None


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    reason: str


class ModelFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[ModelEntry] = Field(min_length=1)
    decision: Decision | None = None


class QuestionResult(BaseModel):
    id: str
    status: Status | None
    # The types of the charts that the answer shows.
    charts: list[str]
    tool_calls: int
    claims_checked: int
    claims_passed: int
    model_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    seconds: float
    expected: list[float]
    # The expected values that no passed claim has.
    missing: list[float]
    correct: bool
    error: str | None = None


class RunFile(BaseModel):
    model: ModelEntry
    run: int
    started_at: str
    results: list[QuestionResult]


def read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise EvalError(f"{path} cannot be read: {error}") from None


def load_golden(path: Path) -> list[GoldenItem]:
    """Return the golden items. Raise EvalError for a file that the evals cannot use."""
    data = read_yaml(path)
    if not isinstance(data, list):
        raise EvalError(f"{path} must be a list of items.")
    items = []
    for number, entry in enumerate(data, start=1):
        try:
            items.append(GoldenItem.model_validate(entry))
        except ValidationError as error:
            raise EvalError(f"{path}, item {number}: {error.errors()[0]['msg']}.") from None
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise EvalError(f"{path} has an id two times.")
    for item in items:
        for sql in item.queries():
            try:
                sql_guard.guard(sql)
            except sql_guard.SqlRejected as error:
                raise EvalError(f"{item.id}: {error}") from None
    return items


def load_models(path: Path) -> ModelFile:
    try:
        return ModelFile.model_validate(read_yaml(path))
    except ValidationError as error:
        raise EvalError(f"{path}: {error.errors()[0]['msg']}.") from None


def expected_values(columns: Sequence[str], rows: Sequence[Sequence[JsonValue]]) -> list[float]:
    """The number cells of the first row: the values that the answer must claim."""
    if not rows:
        raise EvalError("The golden query gave no row.")
    values = [
        cell for cell in rows[0] if isinstance(cell, int | float) and not isinstance(cell, bool)
    ]
    if not values:
        raise EvalError(f"The golden query gave no number in {', '.join(columns)}.")
    return values


def answer_charts(turn: Turn) -> list[str]:
    """The types of the charts that the answer names, from the build_chart records."""
    named = {chart.id for chart in turn.answer.charts}
    types = []
    for record in turn.records:
        chart = record.result.get("chart") if record.name == "build_chart" else None
        if isinstance(chart, dict) and chart.get("id") in named:
            types.append(str(chart.get("type")))
    return types


def cost(usage: Usage, model: ModelEntry) -> float:
    """The same formula as the request log of the API."""
    dollars = (
        usage.input_tokens * model.input_usd_per_mtok
        + usage.output_tokens * model.output_usd_per_mtok
    )
    return round(dollars / 1_000_000, 6)


def is_correct(item: GoldenItem, turn: Turn, missing: list[float]) -> bool:
    if turn.answer.status != item.status:
        return False
    if item.status == "out_of_scope":
        # The scope guard answers without the data.
        return not turn.records
    return not missing


def closest_reading(
    readings: list[list[float]], claimed: list[float]
) -> tuple[list[float], list[float]]:
    """The reading with the fewest values that no claim has, the first one on a tie,
    and those values."""
    options = [
        (reading, [value for value in reading if not any(cell_matches(value, c) for c in claimed)])
        for reading in readings
    ]
    return min(options or [([], [])], key=lambda option: len(option[1]))


def score(
    item: GoldenItem,
    outcome: Turn | AgentError,
    usage: Usage,
    seconds: float,
    readings: list[list[float]],
    model: ModelEntry,
) -> QuestionResult:
    """Score one turn. usage is the usage of the item, its before questions included.
    readings holds the expected values of each fair reading of the question."""
    # The answer of a turn holds only the claims that passed the verifier.
    claimed = [] if isinstance(outcome, AgentError) else [c.value for c in outcome.answer.claims]
    expected, missing = closest_reading(readings, claimed)
    common = {
        "id": item.id,
        "model_calls": usage.model_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": cost(usage, model),
        "seconds": round(seconds, 2),
        "expected": expected,
    }
    if isinstance(outcome, AgentError):
        return QuestionResult(
            **common, status=None, charts=[], tool_calls=0, claims_checked=0,
            claims_passed=0, missing=expected, correct=False, error=str(outcome),
        )  # fmt: skip
    return QuestionResult(
        **common,
        status=outcome.answer.status,
        charts=answer_charts(outcome),
        tool_calls=len(outcome.records),
        claims_checked=outcome.verification.checked,
        claims_passed=outcome.verification.passed,
        missing=missing,
        correct=is_correct(item, outcome, missing),
    )


class Summary(BaseModel):
    """The metrics of one run of one model."""

    questions: int
    correct: int
    verified_rate: float | None
    chart_match: int
    chart_items: int
    refusals_correct: int
    refusal_items: int
    mean_tool_calls: float
    median_seconds: float
    mean_seconds: float
    mean_cost: float
    total_cost: float
    errors: int


def summarize(results: list[QuestionResult], items: list[GoldenItem]) -> Summary:
    by_id = {item.id: item for item in items}
    scored = [(by_id[result.id], result) for result in results if result.id in by_id]
    checked = sum(result.claims_checked for _, result in scored)
    with_chart = [(item, result) for item, result in scored if item.chart]
    refusals = [result for item, result in scored if item.status in REFUSALS]
    seconds = [result.seconds for _, result in scored] or [0.0]
    costs = [result.cost_usd for _, result in scored] or [0.0]
    return Summary(
        questions=len(scored),
        correct=sum(result.correct for _, result in scored),
        verified_rate=(
            sum(result.claims_passed for _, result in scored) / checked if checked else None
        ),
        chart_match=sum(item.chart in result.charts for item, result in with_chart),
        chart_items=len(with_chart),
        refusals_correct=sum(result.correct for result in refusals),
        refusal_items=len(refusals),
        mean_tool_calls=statistics.fmean([r.tool_calls for _, r in scored] or [0]),
        median_seconds=statistics.median(seconds),
        mean_seconds=statistics.fmean(seconds),
        mean_cost=statistics.fmean(costs),
        total_cost=sum(costs),
        errors=sum(result.error is not None for _, result in scored),
    )


def spread(values: list[float], digits: int) -> str:
    """The mean of the runs, and the lowest and highest run when they differ."""
    mean = round(statistics.fmean(values), digits)
    low, high = round(min(values), digits), round(max(values), digits)
    text = f"{mean:.{digits}f}"
    return text if low == high else f"{text} ({low:.{digits}f} to {high:.{digits}f})"


def percent(share: float | None) -> float | None:
    return None if share is None else 100 * share


METRICS: tuple[tuple[str, Callable[[Summary], float | None], int], ...] = (
    ("Correct answers", lambda s: s.correct, 1),
    ("Correct answers (%)", lambda s: 100 * s.correct / s.questions if s.questions else 0, 0),
    ("Verified-claim rate (%)", lambda s: percent(s.verified_rate), 0),
    ("Chart type matches", lambda s: s.chart_match, 1),
    ("Correct refusals", lambda s: s.refusals_correct, 1),
    ("Tool calls per question", lambda s: s.mean_tool_calls, 1),
    ("Median seconds", lambda s: s.median_seconds, 1),
    ("Mean seconds", lambda s: s.mean_seconds, 1),
    ("Cost per question (USD)", lambda s: s.mean_cost, 4),
    ("Cost of a run (USD)", lambda s: s.total_cost, 4),
    ("Errors", lambda s: s.errors, 1),
)  # fmt: skip


def metric_cell(
    summaries: list[Summary], read: Callable[[Summary], float | None], digits: int
) -> str:
    values = [value for value in map(read, summaries) if value is not None]
    return spread(values, digits) if values else "n/a"


def propose(by_model: dict[str, list[Summary]]) -> str | None:
    """The rule of the spec: more correct answers win. A gap of one question or less is a
    tie, and then the lower cost per question wins."""
    if len(by_model) < 2:
        return None
    mean = {model: statistics.fmean(s.correct for s in runs) for model, runs in by_model.items()}
    price = {model: statistics.fmean(s.mean_cost for s in runs) for model, runs in by_model.items()}
    best = max(mean, key=lambda model: mean[model])
    tied = [model for model in mean if mean[best] - mean[model] <= 1]
    return min(tied, key=lambda model: price[model])


def failure_text(item: GoldenItem, result: QuestionResult) -> str:
    if result.error:
        return f"error: {result.error}"
    if result.status != item.status:
        return f"status {result.status}, expected {item.status}"
    if item.status == "out_of_scope":
        return f"{result.tool_calls} tool calls, expected none"
    return "no passed claim for " + ", ".join(f"{value:g}" for value in result.missing)


def results_table(models: list[str], by_model: dict[str, list[Summary]]) -> list[str]:
    lines = [
        "| Metric | " + " | ".join(f"`{m}` ({len(by_model[m])} runs)" for m in models) + " |",
        "|---|" + "---|" * len(models),
    ]
    for name, read, digits in METRICS:
        cells = [metric_cell(by_model[model], read, digits) for model in models]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    totals = [by_model[model][0] for model in models]
    lines.append(
        "| Out of | "
        + " | ".join(
            f"{s.questions} questions, {s.chart_items} charts, {s.refusal_items} refusals"
            for s in totals
        )
        + " |"
    )
    return lines


def expected_text(item: GoldenItem, runs: list[RunFile]) -> str:
    """The expected values of each reading that the answers matched, or the status."""
    readings: list[str] = []
    for run in runs:
        for result in run.results:
            text = ", ".join(f"{value:g}" for value in result.expected)
            if result.id == item.id and text and text not in readings:
                readings.append(text)
    return " or ".join(readings) or item.status


def question_table(models: list[str], runs: list[RunFile], items: list[GoldenItem]) -> list[str]:
    lines = [
        "| Id | Question | Expected | " + " | ".join(f"`{m}`" for m in models) + " |",
        "|---|---|---|" + "---|" * len(models),
    ]
    for item in items:
        cells = []
        for model in models:
            done = [
                r for run in runs if run.model.id == model for r in run.results if r.id == item.id
            ]
            cells.append(f"{sum(r.correct for r in done)} of {len(done)}" if done else "not run")
        lines.append(
            f"| {item.id} | {item.question} | {expected_text(item, runs)} | "
            + " | ".join(cells)
            + " |"
        )
    return lines


METHOD = (
    "## Method",
    "",
    "- Each answered question has hand-written SQL, and the number cells of its first row",
    "  are the expected values.",
    "- A question is correct when the status is the expected status and every expected",
    "  value is the value of a claim that passed the verifier (exact for a whole number,",
    "  0.01 for a decimal). An out-of-scope question must also call no tool.",
    "- The expected values come from the local database, as `analyst_ro`. The local data",
    "  is the same load as production.",
    "- Seconds are the wall time of the scored question. Tokens and cost include the",
    "  questions asked before it in the same conversation.",
)


def price_lines(model_file: ModelFile) -> list[str]:
    lines = [
        "| Model | Input (USD / 1M tokens) | Output (USD / 1M tokens) | Source | Read on | Note |",
        "|---|---|---|---|---|---|",
    ]
    for m in model_file.models:
        lines.append(
            f"| `{m.id}` | {m.input_usd_per_mtok:g} | {m.output_usd_per_mtok:g} | "
            f"{m.price_source} | {m.price_date} | {m.price_note or ''} |"
        )
    return lines


def decision_lines(model_file: ModelFile, by_model: dict[str, list[Summary]]) -> list[str]:
    proposed = propose(by_model)
    lines = [f"The rule of the spec proposes `{proposed}`."] if proposed else []
    if model_file.decision:
        chosen = f"Chosen: `{model_file.decision.model}`. {model_file.decision.reason}"
        lines += ["", chosen] if lines else [chosen]
    return lines or ["No decision yet."]


def render(model_file: ModelFile, runs: list[RunFile], items: list[GoldenItem]) -> str:
    """The markdown of evals/results.md."""
    models = [m.id for m in model_file.models if any(run.model.id == m.id for run in runs)]
    by_model = {
        model: [summarize(run.results, items) for run in runs if run.model.id == model]
        for model in models
    }
    lines = [
        "# Evals",
        "",
        "Generated by `uv run --env-file .env evals`. Do not edit this file: the questions",
        "are in `golden.yaml`, the prices and the decision are in `models.yaml`, and the raw",
        "results are in `runs/`.",
        "",
        f"{len(items)} golden questions.",
        "",
        *METHOD,
        "",
        "## Prices",
        "",
        *price_lines(model_file),
        "",
        "## Results",
        "",
    ]
    if not runs:
        return "\n".join([*lines, "No run yet.", ""])
    by_id = {item.id: item for item in items}
    failed = [
        f"- {r.id}, `{run.model.id}`, run {run.run}: {failure_text(by_id[r.id], r)}"
        for run in runs
        for r in run.results
        if r.id in by_id and not r.correct
    ]
    lines += [
        *results_table(models, by_model),
        "",
        "## Each question",
        "",
        *question_table(models, runs, items),
        "",
        "## Failed questions",
        "",
        *(failed or ["None."]),
        "",
        "## Decision",
        "",
        *decision_lines(model_file, by_model),
    ]
    return "\n".join(lines) + "\n"


def model_slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def read_runs(runs_dir: Path) -> list[RunFile]:
    runs = []
    for path in sorted(runs_dir.glob("*.json")):
        try:
            runs.append(RunFile.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError) as error:
            raise EvalError(f"{path} cannot be read: {type(error).__name__}.") from None
    return sorted(runs, key=lambda run: (run.model.id, run.run))


def add_usage(total: Usage, part: Usage | None) -> None:
    if part is not None:
        total.model_calls += part.model_calls
        total.input_tokens += part.input_tokens
        total.output_tokens += part.output_tokens


def ask_item(
    graph: CompiledStateGraph, item: GoldenItem, clock: Callable[[], float]
) -> tuple[Turn | AgentError, Usage, float]:
    """Ask the item on a new conversation. Return the outcome, the usage, and the seconds."""
    thread = uuid.uuid4().hex
    usage = Usage()
    for question in item.before:
        try:
            add_usage(usage, agent.ask(graph, question, thread).usage)
        except AgentError as error:
            add_usage(usage, error.usage)
            return AgentError(f"A question before failed: {error}"), usage, 0.0
    start = clock()
    outcome: Turn | AgentError
    try:
        outcome = agent.ask(graph, item.question, thread)
        add_usage(usage, outcome.usage)
    except AgentError as error:
        outcome = error
        add_usage(usage, error.usage)
    return outcome, usage, clock() - start


def golden_expected(items: list[GoldenItem]) -> dict[str, list[list[float]]]:
    """Run each golden query and return the values of each reading of each item. A query
    that fails stops the evals before any model call."""
    expected = {}
    for item in items:
        readings = []
        for sql in item.queries():
            result = tools.run_sql(sql)
            if not result.ok:
                raise EvalError(f"{item.id}: the golden query failed: {result.error}")
            try:
                readings.append(expected_values(result.columns, result.rows))
            except EvalError as error:
                raise EvalError(f"{item.id}: {error}") from None
        expected[item.id] = readings
    return expected


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals", description="Ask the golden questions on each model and write the table."
    )
    parser.add_argument("--model", action="append", help="a model id of models.yaml")
    parser.add_argument("--runs", type=int, default=2, help="runs for each model (2)")
    parser.add_argument("--only", action="append", help="a question id, for example q01")
    parser.add_argument("--pause", type=float, default=0, help="seconds between questions")
    parser.add_argument("--report", action="store_true", help="only write results.md again")
    args = parser.parse_args(argv)
    if args.runs < 1 or args.pause < 0:
        parser.error("--runs must be 1 or more, and --pause 0 or more")
    return args


def pick[T](
    wanted: list[str] | None, found: list[T], key: Callable[[T], str], what: str
) -> list[T]:
    if not wanted:
        return found
    unknown = set(wanted) - {key(entry) for entry in found}
    if unknown:
        raise EvalError(f"Unknown {what}: {', '.join(sorted(unknown))}.")
    return [entry for entry in found if key(entry) in wanted]


def load_eval_model(model_id: str) -> BaseChatModel:
    return init_chat_model(model_id, timeout=MODEL_TIMEOUT_SECONDS, max_retries=MODEL_RETRIES)


@dataclass
class Deps:
    """What main reaches outside the process. A test gives its own."""

    load_model: Callable[[str], BaseChatModel] = load_eval_model
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    out: Callable[[str], None] = print


def load_agent(model: ModelEntry, load_model: Callable[[str], BaseChatModel]) -> CompiledStateGraph:
    try:
        return agent.build_agent(load_model(model.id))
    except (AgentError, SettingsError) as error:
        raise EvalError(f"{model.id}: {error}") from None
    except Exception as error:
        # An unknown provider, a package that is not installed, or no API key.
        raise EvalError(f"{model.id} did not load ({type(error).__name__}).") from None


def run_model(
    model: ModelEntry,
    items: list[GoldenItem],
    expected: dict[str, list[list[float]]],
    args: argparse.Namespace,
    runs_dir: Path,
    deps: Deps,
) -> None:
    graph = load_agent(model, deps.load_model)
    for run in range(1, args.runs + 1):
        started = datetime.now(UTC).isoformat(timespec="seconds")
        results: list[QuestionResult] = []
        path = runs_dir / f"{model_slug(model.id)}-run{run}.json"
        for number, item in enumerate(items):
            if number and args.pause:
                deps.sleep(args.pause)
            outcome, usage, seconds = ask_item(graph, item, deps.clock)
            result = score(item, outcome, usage, seconds, expected[item.id], model)
            results.append(result)
            run_file = RunFile(model=model, run=run, started_at=started, results=results)
            # Written after each question, so a stopped run keeps what it did.
            path.write_text(run_file.model_dump_json(indent=2) + "\n", encoding="utf-8")
            mark = "correct" if result.correct else "wrong"
            deps.out(
                f"{model.id} run {run} {item.id} {mark} "
                f"{result.seconds:.1f}s ${result.cost_usd:.4f}"
            )


def main(
    argv: Sequence[str] | None = None, *, evals_dir: Path = EVALS_DIR, deps: Deps | None = None
) -> int:
    args = parse(argv)
    deps = deps or Deps()
    runs_dir = evals_dir / "runs"
    try:
        items = load_golden(evals_dir / "golden.yaml")
        model_file = load_models(evals_dir / "models.yaml")
        if not args.report:
            chosen = pick(args.only, items, lambda item: item.id, "question")
            models = pick(args.model, model_file.models, lambda m: m.id, "model")
            expected = golden_expected(chosen)
            runs_dir.mkdir(parents=True, exist_ok=True)
            for model in models:
                run_model(model, chosen, expected, args, runs_dir, deps)
        report = render(model_file, read_runs(runs_dir), items)
        (evals_dir / "results.md").write_text(report, encoding="utf-8")
    except EvalError as error:
        deps.out(f"Evals stopped: {error}")
        return 1
    deps.out(f"Wrote {evals_dir / 'results.md'}")
    return 0
