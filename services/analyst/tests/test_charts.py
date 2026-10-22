import pytest
from pydantic import TypeAdapter, ValidationError

from analyst import charts

SHOT_COLUMNS = ["x", "y", "xg", "outcome", "minute", "opponent"]


def shot_map(columns, rows):
    return charts.build("shot_map", columns, rows, "Henry shots", "c_00000001")


def compare_bars(columns, rows):
    return charts.build("compare_bars", columns, rows, "Henry and Saka", "c_00000002")


def pass_network(columns, rows):
    return charts.build("pass_network", columns, rows, "Arsenal passes", "c_00000003")


def test_a_shot_map_has_one_shot_for_each_row_in_row_order():
    chart = shot_map(
        SHOT_COLUMNS,
        [[104.0, 36.0, 0.25, "goal", 12, "Everton"], [98.5, 44.0, 0.5, "saved", 70, "Leeds"]],
    )

    assert (chart.type, chart.id, chart.title) == ("shot_map", "c_00000001", "Henry shots")
    assert [shot.model_dump() for shot in chart.shots] == [
        {
            "x": 104.0,
            "y": 36.0,
            "xg": 0.25,
            "outcome": "goal",
            "minute": 12,
            "opponent": "Everton",
            "player": None,
            "season": None,
            "match_date": None,
        },
        {
            "x": 98.5,
            "y": 44.0,
            "xg": 0.5,
            "outcome": "saved",
            "minute": 70,
            "opponent": "Leeds",
            "player": None,
            "season": None,
            "match_date": None,
        },
    ]


def test_a_shot_map_takes_the_columns_of_the_view_in_any_order():
    chart = shot_map(
        ["season", "body_part", "opponent", "player", "minute", "match_date", "outcome", "xg"]
        + ["y", "x"],
        [["2003-04", "left foot", "Everton", "Thierry Henry", 0, "2003-08-16", "goal", 1, 0, 120]],
    )

    assert chart.shots[0].model_dump() == {
        "x": 120.0,
        "y": 0.0,
        "xg": 1.0,
        "outcome": "goal",
        "minute": 0,
        "opponent": "Everton",
        "player": "Thierry Henry",
        "season": "2003-04",
        "match_date": "2003-08-16",
    }


@pytest.mark.parametrize(
    ("columns", "row", "reason"),
    [
        (
            ["x", "y", "outcome", "opponent"],
            [104.0, 36.0, "goal", "Everton"],
            "A shot_map chart needs the columns x, y, xg, outcome, minute, opponent."
            " Missing: xg, minute.",
        ),
        (
            [*SHOT_COLUMNS, "x"],
            [104.0, 36.0, 0.25, "goal", 12, "Everton", 104.0],
            "The query has two columns named x.",
        ),
        (SHOT_COLUMNS, [120.5, 36.0, 0.25, "goal", 12, "Everton"], "Row 2, column x:"),
        (SHOT_COLUMNS, [104.0, -1.0, 0.25, "goal", 12, "Everton"], "Row 2, column y:"),
        (SHOT_COLUMNS, [104.0, 36.0, 1.5, "goal", 12, "Everton"], "Row 2, column xg:"),
        (SHOT_COLUMNS, [104.0, 36.0, None, "goal", 12, "Everton"], "Row 2, column xg:"),
        (SHOT_COLUMNS, [104.0, 36.0, "0.25", "goal", 12, "Everton"], "Row 2, column xg:"),
        (SHOT_COLUMNS, [104.0, 36.0, True, "goal", 12, "Everton"], "Row 2, column xg:"),
        (SHOT_COLUMNS, [104.0, 36.0, "NaN", "goal", 12, "Everton"], "Row 2, column xg:"),
        (SHOT_COLUMNS, [104.0, 36.0, 0.25, "", 12, "Everton"], "Row 2, column outcome:"),
        (SHOT_COLUMNS, [104.0, 36.0, 0.25, "goal", 12.5, "Everton"], "Row 2, column minute:"),
        (SHOT_COLUMNS, [104.0, 36.0, 0.25, "goal", -1, "Everton"], "Row 2, column minute:"),
        (SHOT_COLUMNS, [104.0, 36.0, 0.25, "goal", 12, None], "Row 2, column opponent:"),
    ],
)
def test_a_shot_map_rejects_rows_that_are_not_shots(columns, row, reason):
    good = [104.0, 36.0, 0.25, "goal", 12, "Everton", 104.0][: len(columns)]

    with pytest.raises(charts.ChartRejected) as rejected:
        shot_map(columns, [good, row])

    assert str(rejected.value).startswith(reason)


def test_compare_bars_has_two_series_and_one_metric_for_each_other_column():
    chart = compare_bars(
        ["goals", "player", "xg_per_90", "season"],
        [[30, "Thierry Henry", 0.61, "2003-04"], [14, "Bukayo Saka", 0.4, "2025-26"]],
    )

    assert chart.model_dump() == {
        "type": "compare_bars",
        "id": "c_00000002",
        "title": "Henry and Saka",
        "series": [
            {"player": "Thierry Henry", "season": "2003-04"},
            {"player": "Bukayo Saka", "season": "2025-26"},
        ],
        "metrics": [
            {"name": "goals", "values": [30.0, 14.0]},
            {"name": "xg_per_90", "values": [0.61, 0.4]},
        ],
    }


HENRY = ["Thierry Henry", "2003-04"]
SAKA = ["Bukayo Saka", "2025-26"]


@pytest.mark.parametrize(
    ("columns", "rows", "reason"),
    [
        (
            ["player", "goals"],
            [["Thierry Henry", 30], ["Bukayo Saka", 14]],
            "A compare_bars chart needs the columns player, season. Missing: season.",
        ),
        (
            ["player", "season", "goals"],
            [[*HENRY, 30]],
            "A compare_bars chart needs exactly 2 rows, one for each player. The query returned 1.",
        ),
        (
            ["player", "season", "goals"],
            [[*HENRY, 30], [*SAKA, 14], ["Robert Pires", "2003-04", 14]],
            "A compare_bars chart needs exactly 2 rows, one for each player. The query returned 3.",
        ),
        (
            ["player", "season", "goals"],
            [[*HENRY, 30], [*HENRY, 30]],
            "The two rows are the same player and season: Thierry Henry, 2003-04.",
        ),
        (
            ["player", "season"],
            [HENRY, SAKA],
            "A compare_bars chart needs one metric column or more next to player and season.",
        ),
        (
            ["player", "season", "goals"],
            [[None, "2003-04", 30], [*SAKA, 14]],
            "Row 1, column player:",
        ),
        (
            ["player", "season", "goals", "xa"],
            [[*HENRY, 30, None], [*SAKA, 14, 5.2]],
            "The metric xa is null for Thierry Henry."
            " A comparison uses only metrics that both players have.",
        ),
        (
            ["player", "season", "goals", "team"],
            [[*HENRY, 30, "Arsenal"], [*SAKA, 14, "Arsenal"]],
            "The metric team is not a number that a chart can hold for Thierry Henry.",
        ),
        (
            ["player", "season", "scored"],
            [[*HENRY, 30], [*SAKA, True]],
            "The metric scored is not a number that a chart can hold for Bukayo Saka.",
        ),
        (
            ["player", "season", "goals"],
            [[*HENRY, 10**400], [*SAKA, 14]],
            "The metric goals is not a number that a chart can hold for Thierry Henry.",
        ),
        (
            ["player", "season", "goals"],
            [[*HENRY, 30], [*SAKA, float("inf")]],
            "The metric goals is not a number that a chart can hold for Bukayo Saka.",
        ),
        (
            ["player", "season", "goals", "goals"],
            [[*HENRY, 30, 30], [*SAKA, 14, 14]],
            "The query has two columns named goals.",
        ),
    ],
)
def test_compare_bars_rejects_rows_that_do_not_compare_two_players(columns, rows, reason):
    with pytest.raises(charts.ChartRejected) as rejected:
        compare_bars(columns, rows)

    assert str(rejected.value).startswith(reason)


PASS_COLUMNS = ["player", "recipient", "passes", "x", "y"]


def test_a_pass_network_puts_each_passer_at_the_mean_start_of_their_passes():
    chart = pass_network(
        ["x", "y", "passes", "recipient", "player"],
        [
            [10.0, 10.0, 2, "Thierry Henry", "Patrick Vieira"],
            [20.0, 40.0, 1, "Robert Pires", "Patrick Vieira"],
            [90.0, 30.0, 2, "Robert Pires", "Thierry Henry"],
            [70, 10, 4, "Dennis Bergkamp", "Robert Pires"],
        ],
    )

    assert (chart.type, chart.id, chart.title) == ("pass_network", "c_00000003", "Arsenal passes")
    # Vieira: (2 * 10 + 1 * 20) / 3 = 13.33 and (2 * 10 + 1 * 40) / 3 = 20.
    assert [node.model_dump() for node in chart.nodes] == [
        {"player": "Patrick Vieira", "x": 13.33, "y": 20.0, "passes": 3},
        {"player": "Robert Pires", "x": 70.0, "y": 10.0, "passes": 4},
        {"player": "Thierry Henry", "x": 90.0, "y": 30.0, "passes": 2},
    ]
    # Bergkamp has no pass of his own, so he has no node and the edge to him is left out.
    assert [edge.model_dump() for edge in chart.edges] == [
        {"source": "Patrick Vieira", "target": "Thierry Henry", "passes": 2},
        {"source": "Patrick Vieira", "target": "Robert Pires", "passes": 1},
        {"source": "Thierry Henry", "target": "Robert Pires", "passes": 2},
    ]
    # With no until_minute column, the network is of the whole match.
    assert chart.until_minute is None


WINDOW_COLUMNS = [*PASS_COLUMNS, "until_minute"]


@pytest.mark.parametrize(("minute", "expected"), [(71, 71), (None, None)])
def test_a_pass_network_takes_the_minute_its_passes_stop_from_the_rows(minute, expected):
    chart = pass_network(
        WINDOW_COLUMNS,
        [
            ["Patrick Vieira", "Thierry Henry", 2, 10.0, 10.0, minute],
            ["Thierry Henry", "Patrick Vieira", 1, 90.0, 30.0, minute],
        ],
    )

    assert chart.until_minute == expected


@pytest.mark.parametrize(
    ("second", "reason"),
    [
        (
            65,
            "Row 2: until_minute is 65 here and 71 in row 1. The passes of one network stop at"
            " one minute.",
        ),
        (None, "Row 2: until_minute is None here and 71 in row 1."),
        (131, "Row 2, column until_minute:"),
        ("71", "Row 2, column until_minute:"),
    ],
)
def test_a_pass_network_rejects_an_until_minute_that_is_not_one_minute(second, reason):
    with pytest.raises(charts.ChartRejected) as rejected:
        pass_network(
            WINDOW_COLUMNS,
            [
                ["Patrick Vieira", "Thierry Henry", 2, 10.0, 10.0, 71],
                ["Thierry Henry", "Patrick Vieira", 1, 90.0, 30.0, second],
            ],
        )

    assert str(rejected.value).startswith(reason)


@pytest.mark.parametrize(
    ("columns", "row", "reason"),
    [
        (
            ["player", "recipient", "x", "y"],
            ["Thierry Henry", "Robert Pires", 90.0, 30.0],
            "A pass_network chart needs the columns player, recipient, passes, x, y."
            " Missing: passes.",
        ),
        (PASS_COLUMNS, [None, "Robert Pires", 2, 90.0, 30.0], "Row 2, column player:"),
        (PASS_COLUMNS, ["Thierry Henry", None, 2, 90.0, 30.0], "Row 2, column recipient:"),
        (PASS_COLUMNS, ["Thierry Henry", "Robert Pires", 0, 90.0, 30.0], "Row 2, column passes:"),
        (PASS_COLUMNS, ["Thierry Henry", "Robert Pires", 2.5, 90.0, 30.0], "Row 2, column passes:"),
        (PASS_COLUMNS, ["Thierry Henry", "Robert Pires", 2, 121.0, 30.0], "Row 2, column x:"),
        (PASS_COLUMNS, ["Thierry Henry", "Robert Pires", 2, 90.0, None], "Row 2, column y:"),
        (
            PASS_COLUMNS,
            ["Thierry Henry", "Robert Pires", 10**400, 90.0, 30.0],
            "The pass counts of Thierry Henry are too large for a chart.",
        ),
        (
            [*PASS_COLUMNS, "passes"],
            ["Thierry Henry", "Robert Pires", 2, 90.0, 30.0, 2],
            "The query has two columns named passes.",
        ),
        (
            PASS_COLUMNS,
            ["Patrick Vieira", "Thierry Henry", 1, 30.0, 30.0],
            "Row 2: the pair Patrick Vieira to Thierry Henry is in the rows two times."
            " Group the passes by player and recipient.",
        ),
    ],
)
def test_a_pass_network_rejects_rows_that_are_not_pairs(columns, row, reason):
    good = ["Patrick Vieira", "Thierry Henry", 2, 10.0, 10.0, 2][: len(columns)]

    with pytest.raises(charts.ChartRejected) as rejected:
        pass_network(columns, [good, row])

    assert str(rejected.value).startswith(reason)


def test_an_unknown_chart_type_names_the_known_types():
    with pytest.raises(charts.ChartRejected) as rejected:
        charts.build("pie", SHOT_COLUMNS, [], "Henry shots", "c_00000001")

    assert str(rejected.value) == (
        "Unknown chart type 'pie'. Known types: shot_map, compare_bars, pass_network."
    )


def test_the_title_loses_the_space_at_its_ends():
    assert charts.check_request("shot_map", "  Henry shots \n") == "Henry shots"
    assert charts.check_request("shot_map", "x" * 120) == "x" * 120


@pytest.mark.parametrize("title", ["", "   ", "x" * 121])
def test_a_title_that_is_empty_or_too_long_is_rejected(title):
    with pytest.raises(charts.ChartRejected) as rejected:
        charts.build("shot_map", SHOT_COLUMNS, [], title, "c_00000001")

    assert str(rejected.value) == "The title must have 1 to 120 characters."


CHART_SPEC = TypeAdapter(charts.ChartSpec)


def test_a_chart_survives_the_trip_through_json():
    built = [
        shot_map(SHOT_COLUMNS, [[104.0, 36.0, 0.25, "goal", 12, "Everton"]]),
        compare_bars(["player", "season", "goals"], [[*HENRY, 30], [*SAKA, 14]]),
        pass_network(
            PASS_COLUMNS,
            [
                ["Patrick Vieira", "Thierry Henry", 2, 10.0, 10.0],
                ["Thierry Henry", "Patrick Vieira", 1, 90.0, 30.0],
            ],
        ),
        pass_network(WINDOW_COLUMNS, [["Patrick Vieira", "Thierry Henry", 2, 10.0, 10.0, 71]]),
    ]

    for chart in built:
        assert CHART_SPEC.validate_json(chart.model_dump_json()) == chart


def test_json_of_an_unknown_chart_type_is_not_a_chart():
    with pytest.raises(ValidationError):
        CHART_SPEC.validate_json('{"type": "pie", "id": "c_00000001", "title": "Pie"}')
