"""The ask command: questions on the command line, answers on stdout."""

import argparse
import io
import json
import sys
import traceback
import uuid
from collections.abc import Sequence

from pydantic import JsonValue

from analyst import agent
from analyst.answer import Claim
from analyst.settings import SettingsError
from analyst.verifier import Verification

# The key of a chart that holds its marks. The marks have the name of the key.
CHART_MARKS = {"shot_map": "shots", "pass_network": "nodes"}

Chart = dict[str, JsonValue]


def number_text(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def row_count_text(count: int) -> str:
    return f"{count} row" if count == 1 else f"{count} rows"


def chart_size(chart: Chart) -> str:
    if chart["type"] == "compare_bars":
        return f"{len(chart['metrics']) * len(chart['series'])} bars"
    if chart["type"] == "xg_timeline":
        return f"{sum(len(team['shots']) for team in chart['teams'])} shots"
    marks = CHART_MARKS[chart["type"]]
    return f"{len(chart[marks])} {marks}"


def working_lines(records: list[agent.ToolRecord]) -> list[str]:
    if not records:
        return ["Working: no tool call"]
    lines = ["Working:"]
    for number, record in enumerate(records, start=1):
        result = record.result
        if result.get("error"):
            outcome = f": error: {result['error']}"
        elif "row_count" in result:
            outcome = f": {row_count_text(result['row_count'])}"
        else:
            outcome = f" {json.dumps(record.args, ensure_ascii=False)}"
        lines.append(f"  {number}. {record.name}{outcome}")
        # The guard gives no statement back for SQL that it rejects.
        sql = result.get("sql") or record.args.get("sql")
        if sql:
            lines.append(f"     {sql}")
    return lines


def claim_line(claim: Claim) -> str:
    return f"  - {claim.text} | {number_text(claim.value)} {claim.unit} | {claim.tool_call_id}"


def verification_lines(verification: Verification) -> list[str]:
    if verification.checked:
        counts = f"{verification.passed} of {verification.checked} claims passed"
    else:
        counts = "no claim to check"
    lines = [f"Verification: {counts}"]
    if verification.removed:
        lines.append("Removed:")
        lines.extend(
            f"{claim_line(removed.claim)} | {removed.reason}" for removed in verification.removed
        )
    if verification.unbacked_numbers:
        lines.append(f"Unbacked numbers: {', '.join(verification.unbacked_numbers)}")
    return lines


def turn_lines(question: str, turn: agent.Turn, charts: dict[str, Chart]) -> list[str]:
    """Return the text of one turn. charts holds each chart of the conversation by id."""
    answer = turn.answer
    lines = [f"Question: {question}", f"Status: {answer.status}", f"Summary: {answer.summary}"]
    lines.append("Claims:" if answer.claims else "Claims: none")
    lines.extend(claim_line(claim) for claim in answer.claims)
    lines.extend(verification_lines(turn.verification))
    lines.append("Charts:" if answer.charts else "Charts: none")
    for ref in answer.charts:
        chart = charts.get(ref.id)
        detail = (
            f"{chart['type']} | {chart['title']} | {chart_size(chart)}" if chart else "not found"
        )
        lines.append(f"  - {ref.id} | {detail}")
    if answer.caveats:
        lines.append("Caveats:")
        lines.extend(f"  - {caveat}" for caveat in answer.caveats)
    if answer.alternative:
        lines.append(f"Alternative: {answer.alternative}")
    return lines + working_lines(turn.records)


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ask",
        description="Ask the Highbury analyst. Each question after the first is a follow-up.",
    )
    parser.add_argument("questions", nargs="+", metavar="question")
    parser.add_argument("--debug", action="store_true", help="show the traceback of an error")
    args = parser.parse_args(argv)
    if not all(question.strip() for question in args.questions):
        parser.error("a question is empty")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse(argv)
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            # A pipe on Windows has the code page of the system, which cannot hold
            # each letter of a player name.
            stream.reconfigure(encoding="utf-8")

    thread_id = uuid.uuid4().hex
    charts: dict[str, Chart] = {}
    try:
        graph = agent.build_agent()
        for question in args.questions:
            turn = agent.ask(graph, question, thread_id)
            for record in turn.records:
                chart = record.result.get("chart")
                if chart:
                    charts[chart["id"]] = chart
            print("\n".join(turn_lines(question, turn, charts)), end="\n\n")
    except (SettingsError, agent.AgentError) as error:
        if args.debug:
            traceback.print_exc()
        print(f"ask: {error}", file=sys.stderr)
        return 1
    return 0
