import io
import sys

import pytest
from scripted import SHOTS_SQL, ScriptedModel, answer, calls

from analyst import agent, cli

QUESTION = "Show me Henry's shots."


@pytest.fixture
def model(seeded, monkeypatch):
    """Give the CLI a scripted model in place of the one that ANALYST_MODEL names."""

    def use(*replies) -> ScriptedModel:
        scripted = ScriptedModel(replies=list(replies))
        monkeypatch.setattr(agent, "load_model", lambda: scripted)
        return scripted

    return use


def cited_answer(read: dict[str, dict]):
    """An answer that cites the query and the chart of this turn, and a query that is not."""
    return answer(
        summary="Thierry Henry took 2 shots in 2003-04 with 0.75 xG.",
        claims=[
            {
                "text": "Henry took 2 shots",
                "value": 2,
                "unit": "shots",
                "tool_call_id": read["run_sql"]["call_id"],
            },
            {"text": "Their xG was 0.75", "value": 0.75, "unit": "xG", "tool_call_id": "q_none"},
        ],
        charts=[{"id": read["build_chart"]["chart"]["id"]}, {"id": "c_missing"}],
        caveats=["The xG model is the StatsBomb model."],
    )


def test_an_answer_prints_with_its_claims_its_charts_and_its_working(model, capsys):
    model(
        calls(("resolve_player", {"name": "Titi"})),
        calls(("run_sql", {"sql": "SELECT count(*) AS shots FROM v_shots"})),
        calls(("build_chart", {"chart_type": "shot_map", "sql": SHOTS_SQL, "title": "Henry"})),
        cited_answer,
    )

    code = cli.main([QUESTION])

    out = capsys.readouterr().out
    query_id = out.split("Henry took 2 shots | 2 shots | ")[1].split("\n")[0]
    chart_id = out.split(" | shot_map | Henry | 2 shots")[0].split("- ")[-1]
    assert code == 0
    assert out == (
        f"Question: {QUESTION}\n"
        "Status: answered\n"
        "Summary: Thierry Henry took 2 shots in 2003-04 with 0.75 xG.\n"
        "Claims:\n"
        f"  - Henry took 2 shots | 2 shots | {query_id}\n"
        "Verification: 1 of 2 claims passed\n"
        "Removed:\n"
        "  - Their xG was 0.75 | 0.75 xG | q_none | call_not_found\n"
        "Unbacked numbers: 0.75\n"
        "Charts:\n"
        f"  - {chart_id} | shot_map | Henry | 2 shots\n"
        "  - c_missing | not found\n"
        "Caveats:\n"
        "  - The xG model is the StatsBomb model.\n"
        "Working:\n"
        '  1. resolve_player {"name": "Titi"}\n'
        "  2. run_sql: 1 row\n"
        "     SELECT COUNT(*) AS shots FROM v_shots LIMIT 500\n"
        "  3. build_chart: 2 rows\n"
        "     SELECT * FROM v_shots WHERE player = 'Thierry Henry' LIMIT 500\n"
        "\n"
    )
    assert query_id.startswith("q_") and chart_id.startswith("c_")


def test_an_answer_with_no_data_prints_the_alternative(model, capsys):
    model(
        answer(
            status="unavailable",
            summary="There is no pass data for 2025-26.",
            claims=[],
            alternative="I can show Saka's shot map for 2025-26.",
        )
    )

    assert cli.main(["Show Saka's pass map from 2025-26."]) == 0

    assert capsys.readouterr().out == (
        "Question: Show Saka's pass map from 2025-26.\n"
        "Status: unavailable\n"
        "Summary: There is no pass data for 2025-26.\n"
        "Claims: none\n"
        "Verification: no claim to check\n"
        "Charts: none\n"
        "Alternative: I can show Saka's shot map for 2025-26.\n"
        "Working: no tool call\n"
        "\n"
    )


def test_a_question_out_of_scope_prints_no_tool_call(model, capsys):
    model(answer(status="out_of_scope", summary="I only cover two Arsenal seasons.", claims=[]))

    assert cli.main(["Who will win the Champions League?"]) == 0

    out = capsys.readouterr().out
    assert "Status: out_of_scope\n" in out
    assert out.endswith("Working: no tool call\n\n")


def test_a_tool_error_prints_in_the_working(model, capsys):
    model(calls(("run_sql", {"sql": "DROP TABLE shots"})), answer(claims=[]))

    cli.main([QUESTION])

    out = capsys.readouterr().out
    assert "  1. run_sql: error: Only a SELECT statement is allowed." in out
    # The guard gave no statement back, so the working shows the one that the model sent.
    assert "     DROP TABLE shots\n" in out


def test_each_chart_type_prints_its_size(model, capsys):
    bars = "SELECT player, season, goals, minutes FROM v_player_season WHERE minutes > 0"
    network = (
        "SELECT player, recipient, count(*) AS passes, avg(x) AS x, avg(y) AS y FROM v_passes"
        " WHERE recipient IS NOT NULL GROUP BY player, recipient"
    )
    timeline = "SELECT match_id, team, opponent, minute, xg, is_goal FROM v_shots"
    pace = (
        "SELECT home_team AS team, season, match_date, away_team AS opponent,"
        " home_goals AS goals_for, away_goals AS goals_against FROM v_league_matches"
    )
    ids = []

    def keep_id(next_call):
        def keep(read):
            ids.append(read["build_chart"]["chart"]["id"])
            return calls(("build_chart", next_call))

        return keep

    def all_charts(read):
        ids.append(read["build_chart"]["chart"]["id"])
        return answer(charts=[{"id": chart_id} for chart_id in ids])

    model(
        calls(
            (
                "build_chart",
                {
                    "chart_type": "compare_bars",
                    "sql": bars + " AND player IN ('Thierry Henry', 'Bukayo Saka')",
                    "title": "B",
                },
            )
        ),
        keep_id({"chart_type": "pass_network", "sql": network, "title": "N"}),
        keep_id({"chart_type": "xg_timeline", "sql": timeline, "title": "T"}),
        keep_id({"chart_type": "points_pace", "sql": pace, "title": "P"}),
        all_charts,
    )

    assert cli.main([QUESTION]) == 0

    out = capsys.readouterr().out
    assert " | compare_bars | B | 4 bars\n" in out
    assert " | pass_network | N | 2 nodes\n" in out
    assert " | xg_timeline | T | 2 shots\n" in out
    # The home match of Arsenal in each seeded season.
    assert " | points_pace | P | 2 matches\n" in out


def test_two_questions_are_two_turns_of_one_conversation(model, capsys):
    scripted = model(
        calls(("build_chart", {"chart_type": "shot_map", "sql": SHOTS_SQL, "title": "Henry"})),
        lambda read: answer(charts=[{"id": read["build_chart"]["chart"]["id"]}]),
        lambda read: answer(charts=[{"id": read["build_chart"]["chart"]["id"]}]),
    )

    assert cli.main([QUESTION, "Only the ones inside the box."]) == 0

    asked = [message.content for message in scripted.seen[-1] if message.type == "human"]
    assert asked == [QUESTION, "Only the ones inside the box."]
    first, second = capsys.readouterr().out.split("\n\n")[:2]
    assert first.startswith(f"Question: {QUESTION}\n")
    assert second.startswith("Question: Only the ones inside the box.\n")
    # The second answer shows the chart of the first turn again: it is still found.
    assert " | shot_map | Henry | 2 shots" in second
    assert "Working: no tool call" in second


def test_a_failed_turn_prints_one_line_and_stops(model, capsys):
    scripted = model(ConnectionError("no network"), answer())

    code = cli.main([QUESTION, "Only the ones inside the box."])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err == "ask: The model call failed (ConnectionError).\n"
    assert "Status" not in captured.out
    assert len(scripted.seen) == 1


def test_debug_adds_the_traceback(model, capsys):
    model(ConnectionError("no network"))

    assert cli.main(["--debug", QUESTION]) == 1

    err = capsys.readouterr().err
    assert "Traceback (most recent call last)" in err
    assert err.endswith("ask: The model call failed (ConnectionError).\n")


def test_no_model_name_prints_the_variable(seeded, analyst_model, capsys):
    analyst_model(None)

    assert cli.main([QUESTION]) == 1

    assert capsys.readouterr().err == "ask: ANALYST_MODEL is not set\n"


@pytest.mark.parametrize("arguments", [[], ["   "], [QUESTION, ""]])
def test_no_question_is_a_usage_error(model, capsys, arguments):
    scripted = model(answer())

    with pytest.raises(SystemExit) as stop:
        cli.main(arguments)

    assert stop.value.code == 2
    assert "usage: ask" in capsys.readouterr().err
    assert scripted.seen == []


def test_a_letter_that_the_console_code_page_lacks_prints_to_a_pipe(model, monkeypatch):
    model(answer(summary="Robert Pirès and Nemanja Vidić: x ≥ 102.", claims=[]))
    pipe = io.BytesIO()
    # A pipe on Windows has the code page of the system, which has no "ć" and no "≥".
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(pipe, encoding="cp1252"))

    assert cli.main([QUESTION]) == 0

    sys.stdout.flush()
    assert "Summary: Robert Pirès and Nemanja Vidić: x ≥ 102." in pipe.getvalue().decode("utf-8")
