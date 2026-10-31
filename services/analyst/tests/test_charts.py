from datetime import date, timedelta

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


def xg_timeline(columns, rows):
    return charts.build("xg_timeline", columns, rows, "Arsenal v Liverpool", "c_00000004")


def points_pace(columns, rows):
    return charts.build("points_pace", columns, rows, "Arsenal points pace", "c_00000005")


def pass_map(columns, rows):
    return charts.build("pass_map", columns, rows, "Vieira long passes", "c_00000006")


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


TIMELINE_COLUMNS = ["match_id", "team", "opponent", "minute", "xg", "is_goal", "player"]


def test_an_xg_timeline_adds_up_the_xg_of_each_team_in_minute_order():
    chart = xg_timeline(
        TIMELINE_COLUMNS,
        [
            [7, "Liverpool", "Arsenal", 20, 0.1, False, "Steven Gerrard"],
            [7, "Arsenal", "Liverpool", 31, 0.456, True, "Thierry Henry"],
            [7, "Arsenal", "Liverpool", 12, 0.2, False, "Robert Pirès"],
            [7, "Arsenal", "Liverpool", 31, 0.01, False, None],
        ],
    )

    assert (chart.type, chart.id, chart.title) == (
        "xg_timeline",
        "c_00000004",
        "Arsenal v Liverpool",
    )
    # Arsenal comes first, also when row 1 is a shot of the opponent.
    arsenal, liverpool = chart.teams
    assert (arsenal.team, arsenal.xg) == ("Arsenal", 0.67)
    # Two shots in one minute keep the order of the rows.
    assert [shot.model_dump() for shot in arsenal.shots] == [
        {"minute": 12, "xg": 0.2, "total": 0.2, "is_goal": False, "player": "Robert Pirès"},
        {"minute": 31, "xg": 0.456, "total": 0.66, "is_goal": True, "player": "Thierry Henry"},
        {"minute": 31, "xg": 0.01, "total": 0.67, "is_goal": False, "player": None},
    ]
    assert (liverpool.team, liverpool.xg, len(liverpool.shots)) == ("Liverpool", 0.1, 1)


def test_an_xg_timeline_adds_up_before_it_rounds():
    chart = xg_timeline(
        TIMELINE_COLUMNS,
        [[7, "Arsenal", "Leeds", minute, 0.004, False, None] for minute in (1, 2, 3)],
    )

    # Rounded at each shot, three shots of 0.004 would give 0.
    assert [shot.total for shot in chart.teams[0].shots] == [0.0, 0.01, 0.01]
    assert chart.teams[0].xg == 0.01


def test_an_xg_timeline_draws_a_team_with_no_shot_at_zero():
    chart = xg_timeline(TIMELINE_COLUMNS[:6], [[7, "Arsenal", "Leeds United", 40, 0.3, True]])

    assert chart.teams[1].model_dump() == {"team": "Leeds United", "xg": 0.0, "shots": []}
    assert chart.teams[0].shots[0].player is None


@pytest.mark.parametrize(
    ("columns", "row", "reason"),
    [
        (
            TIMELINE_COLUMNS[:5],
            [7, "Arsenal", "Liverpool", 50, 0.2],
            "A xg_timeline chart needs the columns match_id, team, opponent, minute, xg,"
            " is_goal. Missing: is_goal.",
        ),
        (
            TIMELINE_COLUMNS,
            [8, "Arsenal", "Liverpool", 50, 0.2, False, None],
            "Row 2: match_id is 8 here and 7 in row 1. The shots of one timeline come from"
            " one match.",
        ),
        (
            TIMELINE_COLUMNS,
            [7, "Arsenal", "Everton", 50, 0.2, False, None],
            "Row 2: the teams are Arsenal and Everton here and Arsenal and Liverpool in"
            " row 1. The shots of one timeline come from one match.",
        ),
        (
            TIMELINE_COLUMNS,
            [7, "Arsenal", "Liverpool", 50, 0.2, "true", None],
            "Row 2, column is_goal:",
        ),
        (
            TIMELINE_COLUMNS,
            [7, "Arsenal", "Liverpool", 131, 0.2, False, None],
            "Row 2, column minute:",
        ),
        (TIMELINE_COLUMNS, [7, "Arsenal", "Liverpool", 50, 1.2, False, None], "Row 2, column xg:"),
    ],
)
def test_an_xg_timeline_rejects_rows_that_are_not_shots_of_one_match(columns, row, reason):
    good = [7, "Arsenal", "Liverpool", 10, 0.1, False, None][: len(columns)]

    with pytest.raises(charts.ChartRejected) as rejected:
        xg_timeline(columns, [good, row])

    assert str(rejected.value).startswith(reason)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([], "An xg_timeline chart needs one shot or more."),
        (
            [[7, "Chelsea", "Liverpool", 10, 0.1, False, None]],
            "The teams are Chelsea and Liverpool. An xg_timeline shows an Arsenal match.",
        ),
        (
            [[7, "Arsenal", "Arsenal", 10, 0.1, False, None]],
            "The team and the opponent are both Arsenal in row 1.",
        ),
    ],
)
def test_an_xg_timeline_rejects_rows_with_no_arsenal_match(rows, reason):
    with pytest.raises(charts.ChartRejected) as rejected:
        xg_timeline(TIMELINE_COLUMNS, rows)

    assert str(rejected.value) == reason


PACE_COLUMNS = ["team", "season", "match_date", "opponent", "goals_for", "goals_against"]


def test_a_points_pace_adds_up_the_points_of_each_match_in_date_order():
    chart = points_pace(
        PACE_COLUMNS,
        [
            ["Arsenal", "2003-04", "2003-08-31", "Manchester City", 2, 1],
            ["Arsenal", "2003-04", "2003-08-16", "Everton", 2, 1],
            ["Arsenal", "2003-04", "2003-09-13", "Portsmouth", 1, 1],
            ["Arsenal", "2003-04", "2003-08-24", "Middlesbrough", 0, 4],
        ],
    )

    assert (chart.type, chart.id, chart.title) == (
        "points_pace",
        "c_00000005",
        "Arsenal points pace",
    )
    (line,) = chart.lines
    assert (line.team, line.season, line.points) == ("Arsenal", "2003-04", 7)
    assert [match.model_dump() for match in line.matches] == [
        {
            "matchday": 1,
            "match_date": "2003-08-16",
            "opponent": "Everton",
            "goals_for": 2,
            "goals_against": 1,
            "points": 3,
            "total": 3,
        },
        {
            "matchday": 2,
            "match_date": "2003-08-24",
            "opponent": "Middlesbrough",
            "goals_for": 0,
            "goals_against": 4,
            "points": 0,
            "total": 3,
        },
        {
            "matchday": 3,
            "match_date": "2003-08-31",
            "opponent": "Manchester City",
            "goals_for": 2,
            "goals_against": 1,
            "points": 3,
            "total": 6,
        },
        {
            "matchday": 4,
            "match_date": "2003-09-13",
            "opponent": "Portsmouth",
            "goals_for": 1,
            "goals_against": 1,
            "points": 1,
            "total": 7,
        },
    ]


def test_a_points_pace_puts_the_arsenal_lines_first_by_season():
    chart = points_pace(
        PACE_COLUMNS,
        [
            ["Manchester City", "2025-26", "2025-08-16", "Wolves", 4, 0],
            ["Arsenal", "2025-26", "2025-08-17", "Manchester United", 1, 0],
            ["Chelsea", "2003-04", "2003-08-17", "Liverpool", 2, 1],
            ["Arsenal", "2003-04", "2003-08-16", "Everton", 2, 1],
        ],
    )

    assert [(line.team, line.season) for line in chart.lines] == [
        ("Arsenal", "2003-04"),
        ("Arsenal", "2025-26"),
        ("Chelsea", "2003-04"),
        ("Manchester City", "2025-26"),
    ]


def test_a_points_pace_takes_a_whole_season_of_one_team():
    season = [
        ["Arsenal", "2003-04", (date(2003, 8, 16) + timedelta(weeks=week)).isoformat(), "X", 1, 0]
        for week in range(38)
    ]

    (line,) = points_pace(PACE_COLUMNS, season).lines

    assert (len(line.matches), line.points, line.matches[-1].matchday) == (38, 114, 38)


@pytest.mark.parametrize(
    ("columns", "row", "reason"),
    [
        (
            PACE_COLUMNS[:5],
            ["Arsenal", "2003-04", "2003-08-24", "Middlesbrough", 4],
            "A points_pace chart needs the columns team, season, match_date, opponent,"
            " goals_for, goals_against. Missing: goals_against.",
        ),
        (
            PACE_COLUMNS,
            ["Arsenal", "2003-04", "2003-08-24", "Arsenal", 4, 0],
            "Row 2: the team and the opponent are both Arsenal.",
        ),
        (
            PACE_COLUMNS,
            ["Arsenal", "2003-04", "24/08/03", "Middlesbrough", 4, 0],
            "Row 2: the match_date '24/08/03' is not a date.",
        ),
        (
            PACE_COLUMNS,
            ["Arsenal", "2003-04", "2003-08-16", "Middlesbrough", 4, 0],
            "Row 2: Arsenal has two matches on 2003-08-16 in 2003-04. Give one row for each"
            " match of the team.",
        ),
        (
            PACE_COLUMNS,
            ["Arsenal", "2003-04", "2003-08-24", "Middlesbrough", -1, 0],
            "Row 2, column goals_for:",
        ),
        (
            PACE_COLUMNS,
            ["Arsenal", "2003-04", "2003-08-24", "Middlesbrough", "4", 0],
            "Row 2, column goals_for:",
        ),
    ],
)
def test_a_points_pace_rejects_rows_that_are_not_matches_of_a_team(columns, row, reason):
    good = ["Arsenal", "2003-04", "2003-08-16", "Everton", 2, 1][: len(columns)]

    with pytest.raises(charts.ChartRejected) as rejected:
        points_pace(columns, [good, row])

    assert str(rejected.value).startswith(reason)


def test_a_points_pace_rejects_more_than_a_season_of_matches():
    rows = [
        ["Arsenal", "2003-04", (date(2003, 8, 16) + timedelta(days=day)).isoformat(), "X", 1, 0]
        for day in range(39)
    ]

    with pytest.raises(charts.ChartRejected) as rejected:
        points_pace(PACE_COLUMNS, rows)

    assert str(rejected.value) == (
        "Arsenal has more than 38 matches in 2003-04. Give one row for each league match"
        " of the team."
    )


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([], "A points_pace chart needs Arsenal in one season or more."),
        (
            [["Chelsea", "2003-04", "2003-08-17", "Liverpool", 2, 1]],
            "A points_pace chart needs Arsenal in one season or more.",
        ),
        (
            [
                [team, season, "2003-08-16", "X", 1, 0]
                for team in ("Arsenal", "Chelsea", "Liverpool")
                for season in ("2003-04", "2025-26")
            ],
            "The rows make 6 lines. A points_pace chart has 4 lines at most, one for each"
            " team and season.",
        ),
    ],
)
def test_a_points_pace_rejects_lines_that_are_not_an_arsenal_comparison(rows, reason):
    with pytest.raises(charts.ChartRejected) as rejected:
        points_pace(PACE_COLUMNS, rows)

    assert str(rejected.value) == reason


ARROW_COLUMNS = ["x", "y", "end_x", "end_y", "outcome", "minute", "opponent", "player"]
VIEIRA_PASS = [40.0, 30.0, 90.0, 10.0, None, 12, "Everton", "Patrick Vieira"]


def test_a_pass_map_has_one_arrow_for_each_pass_in_row_order():
    chart = pass_map(
        [*ARROW_COLUMNS, "recipient", "match_date"],
        [
            [*VIEIRA_PASS, "Thierry Henry", "2003-08-16"],
            [60, 70, 120, 0, "out", 81, "Leeds United", "Patrick Vieira", None, None],
        ],
    )

    assert (chart.type, chart.id, chart.title) == ("pass_map", "c_00000006", "Vieira long passes")
    assert [arrow.model_dump() for arrow in chart.passes] == [
        {
            "x": 40.0,
            "y": 30.0,
            "end_x": 90.0,
            "end_y": 10.0,
            "outcome": None,
            "minute": 12,
            "opponent": "Everton",
            "player": "Patrick Vieira",
            "recipient": "Thierry Henry",
            "season": None,
            "match_date": "2003-08-16",
        },
        {
            "x": 60.0,
            "y": 70.0,
            "end_x": 120.0,
            "end_y": 0.0,
            "outcome": "out",
            "minute": 81,
            "opponent": "Leeds United",
            "player": "Patrick Vieira",
            "recipient": None,
            "season": None,
            "match_date": None,
        },
    ]


@pytest.mark.parametrize(
    ("columns", "row", "reason"),
    [
        (
            ARROW_COLUMNS[:4] + ARROW_COLUMNS[5:],
            [40.0, 30.0, 90.0, 10.0, 12, "Everton", "Patrick Vieira"],
            "A pass_map chart needs the columns x, y, end_x, end_y, outcome, minute,"
            " opponent, player. Missing: outcome.",
        ),
        (
            ARROW_COLUMNS,
            [40.0, 30.0, 90.0, 10.0, None, 30, "Everton", "Thierry Henry"],
            "Row 2: the player is Thierry Henry here and Patrick Vieira in row 1."
            " A pass_map draws the passes of one player; filter on one player.",
        ),
        (
            ARROW_COLUMNS,
            [40.0, 30.0, 121.0, 10.0, None, 30, "Everton", "Patrick Vieira"],
            "Row 2, column end_x:",
        ),
        (
            ARROW_COLUMNS,
            [40.0, 30.0, 90.0, 80.5, None, 30, "Everton", "Patrick Vieira"],
            "Row 2, column end_y:",
        ),
        (
            ARROW_COLUMNS,
            [40.0, 30.0, 90.0, 10.0, "", 30, "Everton", "Patrick Vieira"],
            "Row 2, column outcome:",
        ),
        (
            ARROW_COLUMNS,
            [40.0, 30.0, 90.0, 10.0, None, 30, "Everton", None],
            "Row 2, column player:",
        ),
    ],
)
def test_a_pass_map_rejects_rows_that_are_not_passes_of_one_player(columns, row, reason):
    good = [c for name, c in zip(ARROW_COLUMNS, VIEIRA_PASS, strict=True) if name in columns]

    with pytest.raises(charts.ChartRejected) as rejected:
        pass_map(columns, [good, row])

    assert str(rejected.value).startswith(reason)


def test_an_unknown_chart_type_names_the_known_types():
    with pytest.raises(charts.ChartRejected) as rejected:
        charts.build("pie", SHOT_COLUMNS, [], "Henry shots", "c_00000001")

    assert str(rejected.value) == (
        "Unknown chart type 'pie'. Known types: shot_map, compare_bars, pass_network,"
        " xg_timeline, points_pace, pass_map."
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
        xg_timeline(TIMELINE_COLUMNS, [[7, "Arsenal", "Liverpool", 31, 0.45, True, "Henry"]]),
        points_pace(PACE_COLUMNS, [["Arsenal", "2003-04", "2003-08-16", "Everton", 2, 1]]),
        pass_map(ARROW_COLUMNS, [VIEIRA_PASS]),
    ]

    for chart in built:
        assert CHART_SPEC.validate_json(chart.model_dump_json()) == chart


def test_json_of_an_unknown_chart_type_is_not_a_chart():
    with pytest.raises(ValidationError):
        CHART_SPEC.validate_json('{"type": "pie", "id": "c_00000001", "title": "Pie"}')
