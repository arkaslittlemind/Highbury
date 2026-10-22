import pytest

from analyst import prompt, tools
from analyst.sql_guard import AGENT_VIEWS
from ingest.curated import CATALOG


@pytest.fixture
def text(seeded) -> str:
    return prompt.build_system_prompt(tools.get_data_catalog(), tools.get_schema())


def test_the_prompt_holds_each_catalog_row(text):
    lines = text.splitlines()

    for season, metric, available, _source, notes in CATALOG:
        word = "available" if available else "not available"
        row = [line for line in lines if line.startswith(f"- {season} | {metric} | {word} | ")]
        assert len(row) == 1, (season, metric)
        assert notes in row[0]


def test_the_prompt_holds_each_view_with_each_column_and_its_comment(text):
    views = tools.get_schema().views
    assert [view.name for view in views] == list(AGENT_VIEWS)

    for view in views:
        assert f"{view.name}: {view.description}" in text
        for column in view.columns:
            assert f"- {column.name} ({column.type}): {column.description}" in text
    assert "One row per pass. 2003-04 only: no pass data exists for 2025-26." in text
    assert "- is_goal (boolean): True when the shot was a goal." in text


@pytest.mark.parametrize(
    "rule",
    [
        "call no tool and give the status out_of_scope",
        "Read the data catalog before a claim about a season",
        "give the status unavailable",
        "in alternative",
        "Season labels are 2003-04 and 2025-26, with a hyphen",
        "Resolve each player name with resolve_player",
        "ask which player",
        "never calculate a number yourself",
        "Every number in the summary has a claim",
        "the call_id of a run_sql result of this question whose rows hold the value",
        "To give a number of an earlier answer again, run its query again",
        "only metrics that both seasons have",
        "StatsBomb for 2003-04, Understat for 2025-26",
        "Use build_chart to show rows and run_sql for the numbers of the claims",
        "only chart ids that build_chart returned in this conversation",
        "x >= 102 AND y BETWEEN 18 AND 62",
    ],
)
def test_the_prompt_holds_each_rule(text, rule):
    assert rule in text


def test_the_prompt_holds_the_sql_examples(text):
    assert 4 <= len(prompt.SQL_EXAMPLES) <= 8
    for purpose, sql in prompt.SQL_EXAMPLES:
        assert purpose in text
        assert sql in text


@pytest.mark.parametrize("sql", [sql for _, sql in prompt.SQL_EXAMPLES])
def test_each_sql_example_runs_on_the_views(seeded, sql):
    result = tools.run_sql(sql)

    assert result.ok, result.error


def test_the_shot_examples_make_charts(seeded):
    by_purpose = dict(prompt.SQL_EXAMPLES)

    chart = tools.build_chart("shot_map", by_purpose[prompt.SHOT_MAP_EXAMPLE], "Henry's shots")

    assert chart.ok, chart.error
    assert len(chart.chart.shots) == 2


def test_the_pass_examples_make_a_network_and_its_totals(liverpool_home):
    by_purpose = dict(prompt.SQL_EXAMPLES)

    chart = tools.build_chart(
        "pass_network", by_purpose[prompt.PASS_NETWORK_EXAMPLE], "Arsenal v Liverpool"
    )
    totals = tools.run_sql(by_purpose[prompt.PASS_TOTALS_EXAMPLE])

    assert chart.ok, chart.error
    # The failed pass of Henry, the pass of Liverpool, and the pass of Edu after the
    # substitution are not in the network.
    assert [node.model_dump() for node in chart.chart.nodes] == [
        {"player": "Robert Pirès", "x": 50.0, "y": 30.0, "passes": 1},
        {"player": "Thierry Henry", "x": 70.0, "y": 30.0, "passes": 2},
    ]
    assert [edge.model_dump() for edge in chart.chart.edges] == [
        {"source": "Robert Pirès", "target": "Thierry Henry", "passes": 1},
        {"source": "Thierry Henry", "target": "Robert Pirès", "passes": 2},
    ]
    assert chart.chart.until_minute == 71
    # The claims count the same passes that the chart draws, and back its minute.
    assert totals.ok, totals.error
    assert (totals.columns, totals.rows) == (
        ["completed_passes", "passers", "until_minute"],
        [[3, 2, 71]],
    )


def test_the_pass_examples_keep_first_half_stoppage_passes_before_a_half_time_change(
    liverpool_home_half_time,
):
    by_purpose = dict(prompt.SQL_EXAMPLES)

    chart = tools.build_chart(
        "pass_network", by_purpose[prompt.PASS_NETWORK_EXAMPLE], "Arsenal v Liverpool"
    )
    totals = tools.run_sql(by_purpose[prompt.PASS_TOTALS_EXAMPLE])

    assert chart.ok, chart.error
    # Henry's pass at 46:10 of the first half is in. Edu's pass at 45:30 of the second
    # half is out, although its clock reads earlier.
    assert [node.model_dump() for node in chart.chart.nodes] == [
        {"player": "Robert Pirès", "x": 40.0, "y": 20.0, "passes": 1},
        {"player": "Thierry Henry", "x": 80.0, "y": 30.0, "passes": 2},
    ]
    assert chart.chart.until_minute == 45
    assert totals.ok, totals.error
    assert totals.rows == [[3, 2, 45]]


def test_the_pass_examples_keep_every_pass_of_a_match_with_no_substitution(
    liverpool_home_no_substitution,
):
    by_purpose = dict(prompt.SQL_EXAMPLES)

    chart = tools.build_chart(
        "pass_network", by_purpose[prompt.PASS_NETWORK_EXAMPLE], "Arsenal v Liverpool"
    )

    assert chart.ok, chart.error
    assert [node.passes for node in chart.chart.nodes] == [1, 1]
    assert chart.chart.until_minute is None
