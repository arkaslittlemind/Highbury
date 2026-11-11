import json
from pathlib import Path

import pytest

from analyst import match_reports
from analyst.agent import NO_BUDGET, AgentError, Turn, Usage
from analyst.answer import Answer, Claim, ToolRecord
from analyst.match_reports import Deps, MatchInfo, MatchReportError
from analyst.verifier import verify

MATCH_COLUMNS = [
    "match_id",
    "season",
    "match_date",
    "home_team",
    "away_team",
    "home_goals",
    "away_goals",
]
LIVERPOOL = [2, "2003-04", "2004-04-09", "Arsenal", "Liverpool", 4, 2]
BOLTON = [5, "2003-04", "2004-05-01", "Bolton Wanderers", "Arsenal", 2, 2]
FOREST = [212, "2025-26", "2026-01-17", "Nottingham Forest", "Arsenal", 0, 0]
MATCHES = [LIVERPOOL, BOLTON, FOREST]

TIMELINE_COLUMNS = ["match_id", "team", "opponent", "minute", "xg", "is_goal", "player"]
NETWORK_COLUMNS = ["player", "recipient", "passes", "x", "y", "until_minute"]
NETWORK_ROWS = [
    ["Patrick Vieira", "Thierry Henry", 12, 60.0, 40.0, 70],
    ["Thierry Henry", "Patrick Vieira", 8, 80.0, 30.0, 70],
]


class FakeDatabase:
    """Fixed rows for the match list and the chart queries. It keeps the SQL it ran."""

    def __init__(self, matches=MATCHES, timeline_teams=None):
        self.matches = matches
        self.timeline_teams = timeline_teams
        self.queries: list[str] = []

    def read(self, sql: str):
        self.queries.append(sql)
        if sql == match_reports.MATCHES_SQL:
            return MATCH_COLUMNS, [list(row) for row in self.matches]
        match = next(row for row in self.matches if f"match_id = {row[0]}" in sql)
        if sql.startswith("SELECT match_id, team"):
            home, away = self.timeline_teams or (match[3], match[4])
            return TIMELINE_COLUMNS, [
                [match[0], home, away, 10, 0.3, True, "A"],
                [match[0], away, home, 50, 0.1, False, "B"],
            ]
        if sql.startswith("SELECT player, recipient"):
            return NETWORK_COLUMNS, [list(row) for row in NETWORK_ROWS]
        raise AssertionError(f"unexpected SQL: {sql}")


def turn(
    summary: str = "Arsenal won 4-2.",
    values: tuple[float, ...] = (4, 2),
    cited: tuple[float, ...] = (4, 2),
    status: str = "answered",
) -> Turn:
    """A turn as agent.ask returns it: the verifier ran over its claims."""
    record = ToolRecord(
        name="run_sql",
        args={"sql": "SELECT 4, 2"},
        result={
            "call_id": "q1",
            "ok": True,
            "sql": "SELECT home_goals, away_goals FROM v_matches",
            "columns": ["home_goals", "away_goals"],
            "rows": [list(cited)],
        },
    )
    answer = Answer(
        status=status,
        summary=summary,
        claims=[
            Claim(text=f"{value:g} goals", value=value, unit="goals", tool_call_id="q1")
            for value in values
        ],
        charts=[],
        caveats=["Shots only."],
        alternative=None,
    )
    checked, verification = verify(answer, [record])
    usage = Usage(model_calls=2, input_tokens=1000, output_tokens=100)
    return Turn(answer=checked, records=[record], verification=verification, usage=usage)


GOOD = turn()
REMOVED = turn(cited=(4, 3))
UNBACKED = turn(summary="Arsenal won 4-2 with 17 shots.")
NO_CLAIM = turn(summary="Arsenal won.", values=())
UNAVAILABLE = turn(status="unavailable", summary="No data.", values=())


def failed() -> AgentError:
    return AgentError("The model call failed (TimeoutError).", Usage(model_calls=1))


def out_of_credit() -> AgentError:
    error = AgentError(NO_BUDGET, Usage(model_calls=1))
    cause = Exception("payment required")
    cause.code = 402
    error.__cause__ = cause
    return error


class FakeAgent:
    """Gives the outcomes of the test in order and keeps the questions."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.questions: list[str] = []

    def __call__(self, question: str) -> Turn:
        self.questions.append(question)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def run(tmp_path: Path, fake: FakeAgent, argv=(), database=None, model="m:one"):
    database = database or FakeDatabase()
    lines: list[str] = []
    built: list[int] = []

    def build_ask():
        built.append(1)
        return fake

    deps = Deps(
        read=database.read,
        model_name=lambda: model,
        build_ask=build_ask,
        today=lambda: "2026-11-12",
        sleep=lambda seconds: None,
        out=lines.append,
        output=tmp_path / "match-reports.json",
        models_file=tmp_path / "models.yaml",
    )
    status = match_reports.main(list(argv), deps=deps)
    data = json.loads(deps.output.read_text(encoding="utf-8")) if deps.output.exists() else None
    return status, data, lines, built


def slugs(entries: list[dict]) -> list[str]:
    return [entry["slug"] for entry in entries]


def info(row) -> MatchInfo:
    return MatchInfo(**dict(zip(MATCH_COLUMNS, row, strict=True)))


# The match list and the charts.


def test_the_slug_is_the_date_and_the_opponent_in_kebab_case():
    assert info(LIVERPOOL).slug == "2004-04-09-liverpool"
    assert info(FOREST).slug == "2026-01-17-nottingham-forest"
    assert match_reports.slug_of("2004-01-01", "Brighton & Hove Albion!") == (
        "2004-01-01-brighton-hove-albion"
    )


def test_two_matches_with_one_slug_stop_the_run():
    database = FakeDatabase(
        matches=[LIVERPOOL, [9, "2003-04", "2004-04-09", "Liverpool", "Arsenal", 0, 1]]
    )
    with pytest.raises(MatchReportError, match="2004-04-09-liverpool"):
        match_reports.load_matches(database.read)


def test_a_2003_04_match_has_a_timeline_and_a_pass_network():
    built = match_reports.match_charts(info(LIVERPOOL), FakeDatabase().read)
    assert [chart["type"] for chart in built] == ["xg_timeline", "pass_network"]
    assert [chart["id"] for chart in built] == [
        "2004-04-09-liverpool-xg",
        "2004-04-09-liverpool-network",
    ]
    assert built[0]["title"] == "Arsenal 4-2 Liverpool, 2003-04"
    assert built[1]["until_minute"] == 70


def test_a_2025_26_match_has_only_a_timeline():
    database = FakeDatabase()
    built = match_reports.match_charts(info(FOREST), database.read)
    assert [chart["type"] for chart in built] == ["xg_timeline"]
    assert not any("v_passes" in sql for sql in database.queries)


def test_a_chart_that_fails_names_its_match():
    database = FakeDatabase(timeline_teams=("Chelsea", "Fulham"))
    with pytest.raises(MatchReportError, match="2004-04-09-liverpool"):
        match_reports.match_charts(info(LIVERPOOL), database.read)


def test_the_network_sql_keeps_the_passes_before_the_first_change():
    sql = match_reports.network_sql(2)
    assert "match_id = 2" in sql
    assert "outcome IS NULL" in sql
    assert "< ALL (SELECT period, minute, second FROM v_substitutions" in sql


def test_the_question_asks_for_passes_only_in_2003_04():
    liverpool = match_reports.report_question(info(LIVERPOOL))
    forest = match_reports.report_question(info(FOREST))
    assert "at home to Liverpool on 9 April 2004 (2003-04)" in liverpool
    assert "passing" in liverpool
    assert "away at Nottingham Forest on 17 January 2026 (2025-26)" in forest
    assert "pass" not in forest
    assert "Do not draw a chart." in forest


# The keep rule.


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (REMOVED, "removed claims: value_not_found (2 goals)"),
        (UNBACKED, "unbacked numbers: 17"),
        (NO_CLAIM, "no claim"),
        (UNAVAILABLE, "status unavailable"),
    ],
)
def test_a_turn_that_cannot_be_published_says_why(bad, reason):
    assert match_reports.failure(bad) == reason
    assert match_reports.failure(GOOD) is None


def test_a_report_that_passes_first_is_kept(tmp_path):
    fake = FakeAgent(GOOD, GOOD, GOOD)
    status, data, lines, _ = run(tmp_path, fake)
    assert status == 0
    assert slugs(data["reports"]) == [
        "2004-04-09-liverpool",
        "2004-05-01-bolton-wanderers",
        "2026-01-17-nottingham-forest",
    ]
    report = data["reports"][0]
    assert report["attempts"] == 1
    assert report["home_goals"] == 4 and "match_id" not in report
    assert report["summary"] == "Arsenal won 4-2."
    assert report["claims"][0] == {
        "text": "4 goals",
        "value": 4,
        "unit": "goals",
        "sql": "SELECT home_goals, away_goals FROM v_matches",
    }
    assert report["verification"] == {
        "checked": 2,
        "passed": 2,
        "removed": [],
        "unbacked_numbers": [],
    }
    assert data["left_out"] == []
    assert "3 kept, 0 left out" in lines


def test_a_report_that_passes_on_the_third_attempt_is_kept(tmp_path):
    fake = FakeAgent(REMOVED, failed(), GOOD)
    status, data, _, _ = run(tmp_path, fake, ["--only", "2004-04-09-liverpool"])
    assert status == 0
    assert data["reports"][0]["attempts"] == 3
    # Each attempt asks the same question again.
    assert len(set(fake.questions)) == 1 and len(fake.questions) == 3


def test_a_report_that_fails_three_times_is_left_out_with_each_reason(tmp_path):
    fake = FakeAgent(UNBACKED, failed(), UNAVAILABLE, GOOD, GOOD)
    status, data, lines, _ = run(tmp_path, fake)
    assert status == 0
    assert slugs(data["reports"]) == ["2004-05-01-bolton-wanderers", "2026-01-17-nottingham-forest"]
    entry = data["left_out"][0]
    assert entry["slug"] == "2004-04-09-liverpool"
    assert entry["home_team"] == "Arsenal"
    assert entry["reasons"] == [
        "unbacked numbers: 17",
        "error: The model call failed (TimeoutError).",
        "status unavailable",
    ]
    assert "2 kept, 1 left out: 2004-04-09-liverpool" in lines


def test_out_of_credit_stops_the_run_and_keeps_what_was_written(tmp_path):
    fake = FakeAgent(GOOD, out_of_credit(), GOOD)
    status, data, lines, _ = run(tmp_path, fake)
    assert status == 1
    assert len(fake.questions) == 2
    assert slugs(data["reports"]) == ["2004-04-09-liverpool"]
    assert any("payment" in line and "2004-05-01-bolton-wanderers" in line for line in lines)
    # The usage of the paid calls is still reported.
    assert "3 model calls, 1000 input and 100 output tokens, cost unknown" in lines


# The file, resume, and the arguments.


def test_a_second_run_asks_only_the_matches_with_no_kept_report(tmp_path):
    run(tmp_path, FakeAgent(UNBACKED, UNBACKED, UNBACKED, GOOD, GOOD))
    fake = FakeAgent(GOOD)
    status, data, _, _ = run(tmp_path, fake)
    assert status == 0
    assert len(fake.questions) == 1 and "Liverpool" in fake.questions[0]
    assert len(data["reports"]) == 3 and data["left_out"] == []


def test_limit_asks_a_batch_and_the_next_run_goes_on(tmp_path):
    fake = FakeAgent(GOOD)
    status, data, lines, _ = run(tmp_path, fake, ["--limit", "1"])
    assert status == 0 and len(fake.questions) == 1
    assert slugs(data["reports"]) == ["2004-04-09-liverpool"]
    assert "2 matches not asked yet" in lines
    fake = FakeAgent(GOOD, GOOD)
    status, data, lines, _ = run(tmp_path, fake, ["--limit", "5"])
    assert status == 0 and len(fake.questions) == 2
    assert len(data["reports"]) == 3
    assert not any("not asked yet" in line for line in lines)


def test_a_batch_asks_new_matches_before_left_out_ones(tmp_path):
    run(tmp_path, FakeAgent(UNBACKED, UNBACKED, UNBACKED), ["--limit", "1"])
    fake = FakeAgent(GOOD, GOOD)
    status, data, _, _ = run(tmp_path, fake, ["--limit", "1"])
    assert status == 0 and "Bolton Wanderers" in fake.questions[0]
    assert slugs(data["left_out"]) == ["2004-04-09-liverpool"]
    # With the new matches done, the left-out match is asked again.
    status, data, _, _ = run(tmp_path, fake, ["--limit", "1"])
    assert "Nottingham Forest" in fake.questions[1]
    fake = FakeAgent(GOOD)
    status, data, _, _ = run(tmp_path, fake)
    assert "Liverpool" in fake.questions[0]
    assert len(data["reports"]) == 3 and data["left_out"] == []


def test_nothing_to_ask_loads_no_model(tmp_path):
    run(tmp_path, FakeAgent(GOOD, GOOD, GOOD))
    status, _, lines, built = run(tmp_path, FakeAgent())
    assert status == 0 and built == []
    assert "3 kept, 0 left out" in lines


def test_only_asks_the_named_match_again_and_keeps_the_others(tmp_path):
    run(tmp_path, FakeAgent(GOOD, GOOD, GOOD))
    fake = FakeAgent(turn(summary="Arsenal beat Liverpool 4-2."))
    status, data, _, _ = run(tmp_path, fake, ["--only", "2004-04-09-liverpool"])
    assert status == 0 and len(fake.questions) == 1
    assert data["reports"][0]["summary"] == "Arsenal beat Liverpool 4-2."
    assert len(data["reports"]) == 3


def test_an_unknown_match_stops_before_any_model_loads(tmp_path):
    status, data, lines, built = run(tmp_path, FakeAgent(), ["--only", "2004-04-10-liverpool"])
    assert status == 1 and built == [] and data is None
    assert "Match reports stopped: Unknown match: 2004-04-10-liverpool." in lines


def test_a_file_of_another_model_stops_the_run(tmp_path):
    run(tmp_path, FakeAgent(GOOD, GOOD, GOOD))
    status, _, lines, built = run(
        tmp_path, FakeAgent(), ["--only", "2004-04-09-liverpool"], model="m:two"
    )
    assert status == 1 and built == []
    assert any("made with m:one" in line for line in lines)


def test_the_same_reports_give_the_same_bytes(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    run(first, FakeAgent(GOOD, GOOD, GOOD))
    run(second, FakeAgent(GOOD, GOOD, GOOD))
    text = (first / "match-reports.json").read_bytes()
    assert text == (second / "match-reports.json").read_bytes()
    lines = text.decode("utf-8").splitlines()
    # One line for each report.
    assert sum(line.startswith('    {"slug"') for line in lines) == 3
    assert lines[1] == '  "generated_at": "2026-11-12",'


def test_the_cost_comes_from_the_price_of_the_model(tmp_path):
    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  - id: m:one\n"
        "    input_usd_per_mtok: 1.0\n"
        "    output_usd_per_mtok: 10.0\n"
        "    price_source: test\n"
        '    price_date: "2026-11-12"\n',
        encoding="utf-8",
    )
    _, _, lines, _ = run(tmp_path, FakeAgent(GOOD, GOOD, GOOD))
    # 3000 input tokens at $1 and 300 output tokens at $10 for each million.
    assert "6 model calls, 3000 input and 300 output tokens, $0.0060" in lines


# The committed file. Batches fill it across top-ups, so the test checks what is there.

COMMITTED = Path(__file__).resolve().parents[3] / match_reports.OUTPUT


def test_each_committed_report_passed_every_check():
    data = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert data["max_attempts"] == match_reports.MAX_ATTEMPTS
    reports = data["reports"]
    found = slugs(reports) + slugs(data["left_out"])
    assert len(found) == len(set(found))
    assert "2004-04-09-liverpool" in slugs(reports)
    assert any(report["season"] == "2025-26" for report in reports)
    for report in reports:
        verification = report["verification"]
        assert verification["removed"] == [] and verification["unbacked_numbers"] == []
        assert verification["checked"] == verification["passed"] == len(report["claims"]) >= 1
        assert all(claim["sql"] for claim in report["claims"])
        expected = ["xg_timeline"] + (["pass_network"] if report["season"] == "2003-04" else [])
        assert [chart["type"] for chart in report["charts"]] == expected
