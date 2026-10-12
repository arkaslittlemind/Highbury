import pytest

from analyst.answer import Answer, ToolRecord
from analyst.tools import ChartResult, SqlResult
from analyst.verifier import RemovedClaim, Verification, verify


def query(call_id: str, rows: list[list]) -> ToolRecord:
    """The record of a run_sql call that gave the rows."""
    result = SqlResult(call_id=call_id, ok=True, sql="SELECT 1", rows=rows, row_count=len(rows))
    return ToolRecord(name="run_sql", args={}, result=result.model_dump(mode="json"))


def claim(value: float, tool_call_id: str = "q_1") -> dict:
    return {"text": "A claim", "value": value, "unit": "", "tool_call_id": tool_call_id}


def answer(*claims: dict, summary: str = "", status: str = "answered") -> Answer:
    return Answer(
        status=status, summary=summary, claims=claims, charts=[], caveats=[], alternative=None
    )


def reasons(verification: Verification) -> list[str]:
    return [removed.reason for removed in verification.removed]


def test_a_claim_with_the_value_of_its_cited_rows_passes():
    given = answer(claim(30), claim(0.75), summary="Henry scored 30 goals from 0.75 xG.")

    checked, verification = verify(given, [query("q_1", [["Thierry Henry", 30, 0.75]])])

    assert checked == given
    assert verification == Verification(checked=2, passed=2, removed=[], unbacked_numbers=[])


def test_a_claim_with_a_wrong_value_is_removed():
    wrong = claim(31)
    given = answer(claim(30), wrong)

    checked, verification = verify(given, [query("q_1", [["Thierry Henry", 30]])])

    assert [kept.value for kept in checked.claims] == [30]
    assert verification.checked == 2
    assert verification.passed == 1
    assert verification.removed == [RemovedClaim(claim=wrong, reason="value_not_found")]


def test_a_claim_with_a_wrong_tool_call_id_is_removed():
    wrong = claim(30, "q_none")

    checked, verification = verify(answer(wrong), [query("q_1", [[30]])])

    assert checked.claims == []
    assert verification.passed == 0
    assert verification.removed == [RemovedClaim(claim=wrong, reason="call_not_found")]


def test_a_summary_number_with_no_claim_behind_it_is_flagged():
    given = answer(claim(30), summary="Henry scored 30 goals and gave 6 assists.")

    checked, verification = verify(given, [query("q_1", [[30, 6]])])

    assert checked.summary == given.summary
    assert verification.unbacked_numbers == ["6"]


@pytest.mark.parametrize(
    ("value", "passes"),
    [(0.75, True), (0.76, True), (0.74, True), (0.7601, False), (0.77, False), (0.73, False)],
)
def test_a_float_cell_matches_a_value_that_is_within_one_hundredth(value, passes):
    _, verification = verify(answer(claim(value)), [query("q_1", [[0.75]])])

    assert verification.passed == (1 if passes else 0)


@pytest.mark.parametrize(("value", "passes"), [(30.0, True), (30.004, False), (29.99, False)])
def test_an_integer_cell_matches_only_an_equal_value(value, passes):
    _, verification = verify(answer(claim(value)), [query("q_1", [[30]])])

    assert verification.passed == (1 if passes else 0)


def test_a_value_that_is_only_in_another_query_is_removed():
    records = [query("q_1", [[30]]), query("q_2", [[17]])]

    _, verification = verify(answer(claim(17, "q_1"), claim(17, "q_2")), records)

    assert verification.passed == 1
    assert reasons(verification) == ["value_not_found"]


def test_a_claim_that_cites_a_call_with_no_rows_is_removed():
    failed = SqlResult(call_id="q_failed", ok=False, error="Only a SELECT statement is allowed.")
    chart = ChartResult(ok=True, call_id="q_chart", sql="SELECT 1", row_count=1)
    records = [
        ToolRecord(name="run_sql", args={}, result=failed.model_dump(mode="json")),
        ToolRecord(name="build_chart", args={}, result=chart.model_dump(mode="json")),
        # The call did not reach the tool.
        ToolRecord(name="run_sql", args={}, result={"error": "sql: Field required"}),
        ToolRecord(name="run_sql", args={}, result={"call_id": "q_bad", "rows": "30"}),
        ToolRecord(name="run_sql", args={}, result={"call_id": "q_flat", "rows": [30]}),
    ]
    ids = ["q_failed", "q_chart", "q_none", "q_bad", "q_flat"]

    checked, verification = verify(answer(*(claim(30, call_id) for call_id in ids)), records)

    assert checked.claims == []
    assert reasons(verification) == [
        "value_not_found",
        "call_not_found",
        "call_not_found",
        "value_not_found",
        "value_not_found",
    ]


@pytest.mark.parametrize("value", [30, 1, 0])
def test_only_a_number_cell_can_match(value):
    rows = [[True, False, "30", None, [30], {"n": 30}]]

    _, verification = verify(answer(claim(value)), [query("q_1", rows)])

    assert reasons(verification) == ["value_not_found"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_value_that_is_not_finite_never_matches(value):
    _, verification = verify(answer(claim(value)), [query("q_1", [[30, 0.75]])])

    assert reasons(verification) == ["value_not_found"]


def test_an_answer_with_no_claims_and_no_records_has_an_empty_check():
    given = answer(summary="I only cover Arsenal.", status="out_of_scope")

    checked, verification = verify(given, [])

    assert checked == given
    assert verification == Verification(checked=0, passed=0, removed=[], unbacked_numbers=[])


def test_the_season_labels_and_per_90_are_not_statistics():
    summary = (
        "In 2003-04, 2003\N{EN DASH}04 and 2003/04 Henry had 0.92 goals per 90."
        " In 2025-26, 2025\N{EN DASH}26 and 2025/26 Saka had 0.41 Per 90."
    )

    _, verification = verify(answer(summary=summary), [])

    assert verification.unbacked_numbers == ["0.92", "0.41"]


@pytest.mark.parametrize(
    ("summary", "numbers"),
    [
        ("It was 2003-045.", ["2003", "045"]),
        ("He ran 12003-04 m.", ["12003", "04"]),
        ("It was 4 per 900.", ["4", "900"]),
        ("It was per 90.5.", ["90.5"]),
    ],
)
def test_a_number_that_only_starts_or_ends_like_a_label_is_a_statistic(summary, numbers):
    _, verification = verify(answer(summary=summary), [])

    # The whole number stays. A label inside it must not be taken out.
    assert verification.unbacked_numbers == numbers


def test_a_number_with_thousands_commas_is_one_number():
    records = [query("q_1", [[1234]])]

    _, backed = verify(answer(claim(1234), summary="Arsenal made 1,234 passes."), records)
    _, unbacked = verify(answer(summary="Arsenal made 1,234 passes."), records)

    assert backed.unbacked_numbers == []
    assert unbacked.unbacked_numbers == ["1,234"]


def test_a_summary_number_whose_claim_was_removed_is_flagged():
    given = answer(claim(31), summary="Henry scored 31 goals.")

    _, verification = verify(given, [query("q_1", [[30]])])

    assert verification.unbacked_numbers == ["31"]


def test_a_summary_number_is_backed_as_it_is_written():
    records = [query("q_1", [[-3, 0.7512, 22.87]])]
    given = answer(
        claim(-3),
        claim(0.7512),
        claim(22.87),
        summary="A goal difference of 3, 0.75 xG a match, and about 23 xG in all.",
    )

    _, verification = verify(given, records)

    assert verification.passed == 3
    # 23 has no decimal part, so it is written as a count, and no claim has that count.
    assert verification.unbacked_numbers == ["23"]


def test_each_unbacked_number_is_listed_one_time_in_its_order():
    summary = "He had 2 shots and 2 goals at a rate of 2.0, then 7 more. The score was 2-1."

    _, verification = verify(answer(summary=summary, status="unavailable"), [])

    assert verification.unbacked_numbers == ["2", "2.0", "7", "1"]


def test_the_answer_that_goes_in_is_not_changed():
    given = answer(claim(30), claim(31))
    before = given.model_copy(deep=True)

    checked, _ = verify(given, [query("q_1", [[30]])])

    assert given == before
    assert len(checked.claims) == 1
