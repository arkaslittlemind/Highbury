import itertools
import json
from pathlib import Path

import pytest
from scripted import ScriptedModel, answer, calls, with_usage

from analyst import evals, sql_guard, tools
from analyst.agent import AgentError, Turn, Usage
from analyst.answer import Answer, ChartRef, Claim, ToolRecord
from analyst.verifier import Verification

EVALS_DIR = Path(__file__).resolve().parents[3] / "evals"

MODEL = evals.ModelEntry(
    id="test:model",
    input_usd_per_mtok=1.0,
    output_usd_per_mtok=10.0,
    price_source="https://example.com/pricing",
    price_date="2026-10-14",
)
ANSWERED = evals.GoldenItem(
    id="q01", question="Henry's shots?", status="answered", chart="shot_map", sql="SELECT 1"
)
OUT_OF_SCOPE = evals.GoldenItem(id="q05", question="Who wins the league?", status="out_of_scope")


def turn(
    status="answered",
    values=(),
    removed=0,
    charts=(),
    records=None,
    usage=None,
) -> Turn:
    """A turn whose answer holds the passed claims of values."""
    claims = [Claim(text="n", value=v, unit="n", tool_call_id="q_1") for v in values]
    chart_records = [
        ToolRecord(
            name="build_chart", args={}, result={"ok": True, "chart": {"id": cid, "type": t}}
        )
        for cid, t in charts
    ]
    return Turn(
        answer=Answer(
            status=status,
            summary="s",
            claims=claims,
            charts=[ChartRef(id=cid) for cid, _ in charts],
            caveats=[],
            alternative=None,
        ),
        records=chart_records if records is None else records,
        verification=Verification(
            checked=len(claims) + removed, passed=len(claims), removed=[], unbacked_numbers=[]
        ),
        usage=usage or Usage(model_calls=3, input_tokens=1000, output_tokens=100),
    )


def score(item, outcome, expected=(), seconds=2.0, usage=None, readings=None):
    usage = usage or getattr(outcome, "usage", None) or Usage()
    readings = readings if readings is not None else [list(expected)]
    return evals.score(item, outcome, usage, seconds, readings, MODEL)


def test_the_golden_set_has_15_items_with_sql_on_each_answered_item():
    items = evals.load_golden(EVALS_DIR / "golden.yaml")

    assert [item.id for item in items] == [f"q{n:02d}" for n in range(1, 16)]
    assert {item.status for item in items} == {"answered", "unavailable", "out_of_scope"}
    for item in items:
        assert (item.sql is not None) == (item.status == "answered"), item.id
        if item.sql:
            sql_guard.guard(item.sql)


def test_the_model_file_names_both_models_with_prices():
    model_file = evals.load_models(EVALS_DIR / "models.yaml")

    assert [m.id for m in model_file.models] == [
        "google_genai:gemini-3.8-flash",
        "google_genai:gemini-3.5-flash-lite",
    ]


def test_each_golden_query_runs_on_the_views(seeded):
    items = evals.load_golden(EVALS_DIR / "golden.yaml")

    assert [item.id for item in items if item.also_sql] == ["q02", "q10"]
    for item in items:
        for sql in item.queries():
            result = tools.run_sql(sql)
            assert result.ok, (item.id, result.error)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("- {id: q01, question: Q, status: answered}", "an answered item needs sql"),
        ("- {id: q01, question: Q, status: unavailable, sql: SELECT 1}", "an answered item"),
        ("- {id: q1, question: Q, status: unavailable}", "String should match pattern"),
        ("- {id: q01, question: Q, status: maybe}", "Input should be"),
        ("- {id: q01, question: Q, status: unavailable, extra: 1}", "Extra inputs"),
        ("- {id: q01, question: Q, status: answered, sql: DROP TABLE shots}", "q01:"),
        ("- {id: q01, question: Q, status: unavailable, also_sql: [SELECT 1]}", "only an answered"),
        (
            "- {id: q01, question: Q, status: answered, sql: SELECT 1, also_sql: [DROP TABLE x]}",
            "q01:",
        ),
        (
            "- {id: q01, question: Q, status: unavailable}\n"
            "- {id: q01, question: R, status: unavailable}",
            "an id two times",
        ),
        ("{id: q01}", "must be a list"),
    ],
)
def test_a_golden_file_that_cannot_be_used_is_rejected(tmp_path, text, reason):
    path = tmp_path / "golden.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(evals.EvalError) as error:
        evals.load_golden(path)

    assert reason in str(error.value)


def test_the_expected_values_are_the_numbers_of_the_first_row():
    values = evals.expected_values(["a", "b", "c", "d"], [[30, "Henry", 0.65, True], [1, 2, 3, 4]])

    assert values == [30, 0.65]


@pytest.mark.parametrize(
    ("rows", "reason"), [([], "gave no row"), ([["Henry"]], "gave no number in a")]
)
def test_a_golden_query_with_no_number_is_an_error(rows, reason):
    with pytest.raises(evals.EvalError, match=reason):
        evals.expected_values(["a"], rows)


def test_an_answer_with_each_expected_value_in_a_passed_claim_is_correct():
    result = score(ANSWERED, turn(values=(194, 0.65), charts=[("c1", "shot_map")]), (194, 0.651))

    assert result.correct
    assert result.missing == []
    assert result.charts == ["shot_map"]
    assert (result.claims_checked, result.claims_passed, result.tool_calls) == (2, 2, 1)


def test_a_wrong_value_or_a_value_only_in_a_removed_claim_is_not_correct():
    # The verifier removed the claim of 194, so the answer holds only 30.
    result = score(ANSWERED, turn(values=(30,), removed=1), (194, 30))

    assert not result.correct
    assert result.missing == [194]
    assert (result.claims_checked, result.claims_passed) == (2, 1)


TOTALS = [30, 7, 0.65, 0.35]
PER_90 = [0.81, 0.28, 0.65, 0.35]


def test_an_answer_that_claims_every_value_of_the_second_reading_is_correct():
    result = score(ANSWERED, turn(values=PER_90), readings=[TOTALS, PER_90])

    assert result.correct
    assert (result.expected, result.missing) == (PER_90, [])


def test_an_answer_with_half_of_each_reading_is_wrong_and_names_the_closer_reading():
    result = score(ANSWERED, turn(values=(30, 0.81, 0.28, 0.65)), readings=[TOTALS, PER_90])

    assert not result.correct
    # Per 90 misses only 0.35; the totals miss 7 and 0.35.
    assert (result.expected, result.missing) == (PER_90, [0.35])


def test_with_no_reading_closer_the_first_reading_is_named():
    result = score(ANSWERED, turn(values=()), readings=[TOTALS, PER_90])

    assert (result.expected, result.missing) == (TOTALS, TOTALS)


def test_a_whole_number_must_be_exact_and_a_decimal_within_one_hundredth():
    assert not score(ANSWERED, turn(values=(193.99,)), (194,)).correct
    assert score(ANSWERED, turn(values=(0.66,)), (0.65,)).correct
    assert not score(ANSWERED, turn(values=(0.67,)), (0.65,)).correct


def test_a_wrong_status_is_not_correct():
    result = score(ANSWERED, turn(status="unavailable", values=(194,)), (194,))

    assert not result.correct
    assert result.status == "unavailable"


def test_an_out_of_scope_answer_must_call_no_tool():
    record = ToolRecord(name="get_data_catalog", args={}, result={})

    assert score(OUT_OF_SCOPE, turn(status="out_of_scope")).correct
    assert not score(OUT_OF_SCOPE, turn(status="out_of_scope", records=[record])).correct


def test_the_charts_are_only_the_ones_that_the_answer_names():
    built = ToolRecord(
        name="build_chart", args={}, result={"ok": True, "chart": {"id": "c2", "type": "shot_map"}}
    )
    named = turn(values=(194,), charts=[("c1", "compare_bars")])
    named.records.append(built)

    result = score(ANSWERED, named, (194,))

    # The chart is not part of the correct answer; the chart match is its own metric.
    assert result.correct
    assert result.charts == ["compare_bars"]


def test_a_turn_that_failed_is_a_wrong_result_with_its_usage():
    error = AgentError("The question needed more than 15 model calls.", Usage(model_calls=15))

    result = score(ANSWERED, error, (194,), usage=Usage(model_calls=15, input_tokens=2_000_000))

    assert not result.correct
    assert result.error == "The question needed more than 15 model calls."
    assert (result.model_calls, result.missing, result.status) == (15, [194], None)
    assert result.cost_usd == 2.0


def test_the_cost_uses_the_prices_of_the_model():
    usage = Usage(model_calls=5, input_tokens=50_000, output_tokens=2_000)

    # 50,000 * $1 / 1M + 2,000 * $10 / 1M.
    assert score(ANSWERED, turn(values=(194,), usage=usage), (194,)).cost_usd == 0.07


def result(item_id, correct=True, seconds=2.0, cost=0.01, charts=(), status="answered", **kw):
    return evals.QuestionResult(
        id=item_id, status=status, charts=list(charts), tool_calls=kw.get("tools", 4),
        claims_checked=kw.get("checked", 2), claims_passed=kw.get("passed", 2), model_calls=5,
        input_tokens=1, output_tokens=1, cost_usd=cost, seconds=seconds, expected=[],
        missing=[], correct=correct, error=kw.get("error"),
    )  # fmt: skip


ITEMS = [ANSWERED, OUT_OF_SCOPE]


def test_the_summary_counts_each_metric_of_a_run():
    summary = evals.summarize(
        [
            result("q01", charts=["shot_map"], seconds=4.0, cost=0.03, checked=4, passed=3),
            result("q05", correct=False, status="answered", seconds=1.0, cost=0.01, tools=2),
        ],
        ITEMS,
    )

    assert summary.model_dump() == {
        "questions": 2,
        "correct": 1,
        "verified_rate": 5 / 6,
        "chart_match": 1,
        "chart_items": 1,
        "refusals_correct": 0,
        "refusal_items": 1,
        "mean_tool_calls": 3.0,
        "median_seconds": 2.5,
        "mean_seconds": 2.5,
        "mean_cost": 0.02,
        "total_cost": 0.04,
        "errors": 0,
    }


def test_two_runs_show_the_mean_and_the_range():
    assert evals.spread([12, 14], 1) == "13.0 (12.0 to 14.0)"
    assert evals.spread([13, 13], 1) == "13.0"


def run_file(model, run, *results):
    return evals.RunFile(
        model=model, run=run, started_at="2026-10-14T00:00:00+00:00", results=list(results)
    )


def test_the_report_has_the_prices_the_table_each_question_and_the_failures():
    other = MODEL.model_copy(update={"id": "test:other", "input_usd_per_mtok": 2.0})
    model_file = evals.ModelFile(models=[MODEL, other])
    scope = result("q05", status="out_of_scope")
    runs = [
        run_file(MODEL, 1, result("q01", charts=["shot_map"]), scope),
        run_file(MODEL, 2, result("q01", correct=False, error="boom"), scope),
        run_file(other, 1, result("q01", cost=0.02), scope),
    ]

    text = evals.render(model_file, runs, ITEMS)

    assert "| `test:model` | 1 | 10 | https://example.com/pricing | 2026-10-14 |  |" in text
    assert "| Metric | `test:model` (2 runs) | `test:other` (1 runs) |" in text
    assert "| Correct answers | 1.5 (1.0 to 2.0) | 2.0 |" in text
    assert "| Errors | 0.5 (0.0 to 1.0) | 0.0 |" in text
    assert "| q01 | Henry's shots? | answered | 1 of 2 | 1 of 1 |" in text
    assert "- q01, `test:model`, run 2: error: boom" in text
    # One question apart is a tie, and test:model costs less for each question.
    assert "The rule of the spec proposes `test:model`." in text


def test_the_report_names_each_reading_that_the_answers_matched():
    totals = result("q01").model_copy(update={"expected": [30, 7]})
    per_90 = result("q01").model_copy(update={"expected": [0.81, 0.28]})
    runs = [run_file(MODEL, 1, totals), run_file(MODEL, 2, per_90), run_file(MODEL, 3, totals)]

    text = evals.render(evals.ModelFile(models=[MODEL]), runs, ITEMS)

    assert "| q01 | Henry's shots? | 30, 7 or 0.81, 0.28 | 3 of 3 |" in text


def test_the_report_of_no_run_says_so():
    text = evals.render(evals.ModelFile(models=[MODEL]), [], ITEMS)

    assert text.endswith("## Results\n\nNo run yet.\n")


def test_the_decision_of_the_model_file_goes_into_the_report():
    model_file = evals.ModelFile(
        models=[MODEL], decision=evals.Decision(model="test:model", reason="It is cheaper.")
    )

    text = evals.render(model_file, [run_file(MODEL, 1, result("q01"))], ITEMS)

    assert text.endswith("## Decision\n\nChosen: `test:model`. It is cheaper.\n")


GOLDEN = """
- id: q01
  question: Show me Thierry Henry's shots in 2003-04.
  status: answered
  chart: null
  sql: SELECT count(*) AS shots FROM v_shots WHERE player = 'Thierry Henry'
"""
MODELS = """
models:
  - id: test:model
    input_usd_per_mtok: 1
    output_usd_per_mtok: 10
    price_source: https://example.com/pricing
    price_date: "2026-10-14"
"""


@pytest.fixture
def evals_dir(tmp_path, seeded) -> Path:
    (tmp_path / "golden.yaml").write_text(GOLDEN, encoding="utf-8")
    (tmp_path / "models.yaml").write_text(MODELS, encoding="utf-8")
    return tmp_path


def claimed_answer(read):
    return with_usage(
        answer(
            claims=[
                {
                    "text": "2 shots",
                    "value": 2,
                    "unit": "shots",
                    "tool_call_id": read["run_sql"]["call_id"],
                }
            ]
        ),
        1000,
        200,
    )


def test_a_run_asks_each_question_and_writes_the_run_file_and_the_report(evals_dir):
    count_sql = "SELECT count(*) AS shots FROM v_shots"
    scripted = ScriptedModel(
        replies=[with_usage(calls(("run_sql", {"sql": count_sql})), 1000, 50), claimed_answer]
    )
    printed = []
    ticks = itertools.count(0, 1.5)
    deps = evals.Deps(
        load_model=lambda name: scripted,
        clock=lambda: next(ticks),
        sleep=lambda seconds: None,
        out=printed.append,
    )

    code = evals.main(["--runs", "1"], evals_dir=evals_dir, deps=deps)

    assert code == 0
    saved = json.loads((evals_dir / "runs" / "test-model-run1.json").read_text(encoding="utf-8"))
    (only,) = saved["results"]
    assert (only["id"], only["correct"], only["expected"], only["seconds"]) == (
        "q01",
        True,
        [2],
        1.5,
    )
    # 2,000 * $1 / 1M + 250 * $10 / 1M.
    assert (only["input_tokens"], only["output_tokens"], only["cost_usd"]) == (2000, 250, 0.0045)
    assert printed == [
        "test:model run 1 q01 correct 1.5s $0.0045",
        f"Wrote {evals_dir / 'results.md'}",
    ]
    assert "| q01 | Show me Thierry Henry's shots in 2003-04. | 2 | 1 of 1 |" in (
        evals_dir / "results.md"
    ).read_text(encoding="utf-8")


def test_the_report_mode_calls_no_model(evals_dir):
    (evals_dir / "runs").mkdir()
    printed = []

    def no_model(name):
        raise AssertionError("no model in report mode")

    code = evals.main(
        ["--report"], evals_dir=evals_dir, deps=evals.Deps(load_model=no_model, out=printed.append)
    )

    assert code == 0
    assert "No run yet." in (evals_dir / "results.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (["--only", "q99"], "Unknown question: q99."),
        (["--model", "other:model"], "Unknown model: other:model."),
    ],
)
def test_an_unknown_question_or_model_stops_before_any_model_call(evals_dir, argv, reason):
    printed = []

    code = evals.main(argv, evals_dir=evals_dir, deps=evals.Deps(out=printed.append))

    assert code == 1
    assert printed == [f"Evals stopped: {reason}"]


def test_a_golden_query_that_fails_stops_before_any_model_call(evals_dir):
    (evals_dir / "golden.yaml").write_text(
        GOLDEN.replace("count(*) AS", "count(*) / 0 AS"), encoding="utf-8"
    )
    printed = []

    code = evals.main([], evals_dir=evals_dir, deps=evals.Deps(out=printed.append))

    assert code == 1
    assert printed[0].startswith("Evals stopped: q01")


def test_the_evals_load_a_model_with_a_timeout_and_one_retry(monkeypatch):
    seen = {}
    monkeypatch.setattr(evals, "init_chat_model", lambda name, **options: seen.update(options))

    evals.load_eval_model("google_genai:gemini-3.8-flash")

    assert seen == {"timeout": 120, "max_retries": 1}
    assert evals.Deps().load_model is evals.load_eval_model
