import re

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from scripted import (
    ANSWER,
    COUNT_SQL,
    SHOTS_SQL,
    ScriptedModel,
    answer,
    calls,
    shots_claim,
    tool_texts,
    with_usage,
)

from analyst import agent
from analyst.answer import Answer, Claim
from analyst.settings import SettingsError
from analyst.verifier import Verification


def test_a_turn_returns_the_answer_and_a_record_of_each_tool_call(seeded):
    model = ScriptedModel(
        replies=[
            calls(("resolve_player", {"name": "Titi"})),
            calls(("run_sql", {"sql": "SELECT count(*) AS shots FROM v_shots"})),
            calls(("build_chart", {"chart_type": "shot_map", "sql": SHOTS_SQL, "title": "Henry"})),
            answer(),
        ]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert turn.answer == Answer(**ANSWER)
    assert [record.name for record in turn.records] == ["resolve_player", "run_sql", "build_chart"]
    resolved, query, chart = turn.records
    assert resolved.args == {"name": "Titi"}
    assert resolved.result["matches"][0]["player"] == "Thierry Henry"
    assert query.args == {"sql": "SELECT count(*) AS shots FROM v_shots"}
    assert re.fullmatch(r"q_[0-9a-f]{8}", query.result["call_id"])
    assert query.result["sql"].startswith("SELECT COUNT(*) AS shots FROM v_shots")
    assert query.result["row_count"] == 1
    assert query.result["rows"] == [[2]]
    assert chart.result["chart"]["type"] == "shot_map"
    assert len(chart.result["chart"]["shots"]) == 2


def test_a_claim_that_cites_a_query_of_the_turn_stays_in_the_answer(seeded):
    model = ScriptedModel(
        replies=[
            calls(("run_sql", {"sql": COUNT_SQL})),
            lambda read: answer(claims=[shots_claim(read["run_sql"]["call_id"])]),
        ]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    (claim,) = turn.answer.claims
    assert claim.value == 2
    assert claim.tool_call_id == turn.records[0].result["call_id"]
    assert turn.verification == Verification(checked=1, passed=1, removed=[], unbacked_numbers=[])


def test_a_claim_with_an_unknown_id_is_removed_from_the_answer(seeded):
    model = ScriptedModel(
        replies=[calls(("run_sql", {"sql": COUNT_SQL})), answer(claims=[shots_claim("q_none")])]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert turn.answer.claims == []
    assert (turn.verification.checked, turn.verification.passed) == (1, 0)
    (removed,) = turn.verification.removed
    assert removed.claim == Claim(**shots_claim("q_none"))
    assert removed.reason == "call_not_found"
    # The summary still says the number, and now no claim backs it.
    assert turn.verification.unbacked_numbers == ["2"]


def test_a_claim_in_a_follow_up_cannot_cite_a_query_of_the_turn_before(seeded):
    ids = []

    def first(read):
        ids.append(read["run_sql"]["call_id"])
        return answer(claims=[shots_claim(ids[0])])

    model = ScriptedModel(
        replies=[
            calls(("run_sql", {"sql": COUNT_SQL})),
            first,
            lambda read: answer(claims=[shots_claim(ids[0])]),
        ]
    )
    analyst = agent.build_agent(model)

    before = agent.ask(analyst, "Show me Henry's shots.", "t1")
    follow_up = agent.ask(analyst, "How many was that again?", "t1")

    assert before.verification.passed == 1
    assert follow_up.answer.claims == []
    assert [removed.reason for removed in follow_up.verification.removed] == ["call_not_found"]


def test_the_hooks_get_each_step_before_its_record(seeded):
    model = ScriptedModel(
        replies=[
            calls(("resolve_player", {"name": "Titi"})),
            calls(("run_sql", {"sql": COUNT_SQL})),
            answer(),
        ]
    )
    seen = []

    turn = agent.ask(
        agent.build_agent(model),
        "Show me Henry's shots.",
        "t1",
        on_step=lambda number, tool: seen.append(("step", number, tool)),
        on_record=lambda record: seen.append(("record", record)),
    )

    assert seen == [
        ("step", 1, "resolve_player"),
        ("record", turn.records[0]),
        ("step", 2, "run_sql"),
        ("record", turn.records[1]),
    ]


def test_a_step_comes_before_its_tool_runs(seeded, monkeypatch):
    order = []
    real = agent.tools.run_sql

    def run_sql(sql: str):
        order.append("tool")
        return real(sql)

    run_sql.__doc__ = real.__doc__
    monkeypatch.setattr(agent, "AGENT_TOOLS", [agent.agent_tool(run_sql)])
    model = ScriptedModel(replies=[calls(("run_sql", {"sql": COUNT_SQL})), answer()])

    agent.ask(
        agent.build_agent(model),
        "Show me Henry's shots.",
        "t1",
        on_step=lambda number, tool: order.append("step"),
        on_record=lambda record: order.append("record"),
    )

    assert order == ["step", "tool", "record"]


def test_a_turn_holds_the_tokens_and_the_model_calls_that_it_used(seeded):
    model = ScriptedModel(
        replies=[
            with_usage(calls(("run_sql", {"sql": COUNT_SQL})), 100, 7),
            # A provider that reports no tokens for a reply.
            calls(("run_sql", {"sql": COUNT_SQL})),
            with_usage(answer(), 250, 40),
        ]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert turn.usage == agent.Usage(model_calls=3, input_tokens=350, output_tokens=47)


def test_each_question_has_its_own_usage(seeded):
    model = ScriptedModel(replies=[with_usage(answer(), 100, 7), with_usage(answer(), 30, 2)])
    analyst = agent.build_agent(model)

    agent.ask(analyst, "Show me Henry's shots.", "t1")
    follow_up = agent.ask(analyst, "Only the ones inside the box.", "t1")

    assert follow_up.usage == agent.Usage(model_calls=1, input_tokens=30, output_tokens=2)


def test_the_model_reads_the_full_rows_of_a_query_but_not_the_data_of_a_chart(seeded):
    model = ScriptedModel(
        replies=[
            calls(
                ("run_sql", {"sql": "SELECT count(*) AS shots FROM v_shots"}),
                ("build_chart", {"chart_type": "shot_map", "sql": SHOTS_SQL, "title": "Henry"}),
            ),
            answer(),
        ]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    read = tool_texts(model.seen[-1])
    assert read["run_sql"] == turn.records[0].result
    full = turn.records[1].result
    assert read["build_chart"] == {
        "ok": True,
        "error": None,
        "call_id": full["call_id"],
        "sql": full["sql"],
        "row_count": 2,
        "chart": {"id": full["chart"]["id"], "type": "shot_map", "title": "Henry"},
    }


def test_a_turn_with_no_tool_call_has_no_records(seeded):
    model = ScriptedModel(replies=[answer(status="out_of_scope", claims=[])])

    turn = agent.ask(agent.build_agent(model), "Who will win the Champions League?", "t1")

    assert turn.answer.status == "out_of_scope"
    assert turn.records == []


def test_the_system_prompt_goes_to_the_model(seeded):
    model = ScriptedModel(replies=[answer()])

    agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    system, question = model.seen[0]
    assert "- 2025-26 | passes | not available | " in system.content
    assert question.content == "Show me Henry's shots."


def test_a_call_with_wrong_arguments_is_recorded_with_its_error(seeded):
    model = ScriptedModel(replies=[calls(("run_sql", {"statement": "SELECT 1"})), answer()])

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    (record,) = turn.records
    assert record.name == "run_sql"
    assert record.args == {"statement": "SELECT 1"}
    assert list(record.result) == ["error"]
    assert "sql" in record.result["error"]


@pytest.mark.parametrize("name", ["get_data_catalog", "get_schema"])
def test_the_tools_with_no_required_argument_work(seeded, name):
    model = ScriptedModel(replies=[calls((name, {})), answer()])

    turn = agent.ask(agent.build_agent(model), "What data do you have?", "t1")

    assert turn.records[0].result["error"] is None


def query(number: int) -> AIMessage:
    return calls(("run_sql", {"sql": f"SELECT {number} AS n"}))


def test_the_call_after_the_limit_does_not_run_and_the_turn_fails(seeded):
    assert agent.TOOL_CALL_LIMIT == 10
    model = ScriptedModel(replies=[*(query(number) for number in range(1, 12)), answer()])

    with pytest.raises(agent.AgentError) as error:
        agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert str(error.value) == "The question needed more than 10 tool calls."
    ran = [message for message in model.seen[-1] if isinstance(message, ToolMessage)]
    assert len(ran) == 10
    assert len(model.replies) == 1


def test_a_turn_that_fails_carries_what_it_used(seeded):
    model = ScriptedModel(
        replies=[*(with_usage(query(number), 10, 1) for number in range(1, 12)), answer()]
    )
    steps = []

    with pytest.raises(agent.AgentError) as error:
        agent.ask(
            agent.build_agent(model),
            "Show me Henry's shots.",
            "t1",
            on_step=lambda number, tool: steps.append(number),
        )

    assert error.value.usage == agent.Usage(model_calls=11, input_tokens=110, output_tokens=11)
    # The call over the limit gives no step.
    assert steps == list(range(1, 11))


def test_a_model_call_that_fails_is_counted(seeded):
    model = ScriptedModel(replies=[with_usage(query(1), 10, 1), ConnectionError("no route")])

    with pytest.raises(agent.AgentError) as error:
        agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert error.value.usage == agent.Usage(model_calls=2, input_tokens=10, output_tokens=1)


def test_an_error_before_a_turn_has_no_usage(no_database):
    with pytest.raises(agent.AgentError) as error:
        agent.build_agent(ScriptedModel(replies=[]))

    assert error.value.usage is None


def test_a_follow_up_reads_the_turns_before_it_on_the_same_thread_only(seeded, caplog):
    model = ScriptedModel(replies=[answer(), answer(), answer()])
    analyst = agent.build_agent(model)

    agent.ask(analyst, "Show me Henry's shots.", "t1")
    agent.ask(analyst, "Only the ones inside the box.", "t1")
    agent.ask(analyst, "And Saka?", "t2")

    def questions(messages):
        return [message.content for message in messages if message.type == "human"]

    assert questions(model.seen[1]) == ["Show me Henry's shots.", "Only the ones inside the box."]
    assert questions(model.seen[2]) == ["And Saka?"]
    # The checkpoint reads the answer of the first turn back with no warning.
    assert caplog.records == []


def test_each_turn_has_its_own_records_and_its_own_limit(seeded):
    model = ScriptedModel(
        replies=[
            *(query(number) for number in range(1, 7)),
            answer(),
            *(query(number) for number in range(7, 13)),
            answer(),
        ]
    )
    analyst = agent.build_agent(model)

    first = agent.ask(analyst, "Show me Henry's shots.", "t1")
    second = agent.ask(analyst, "Only the ones inside the box.", "t1")

    assert [record.result["rows"] for record in first.records] == [[[n]] for n in range(1, 7)]
    assert [record.result["rows"] for record in second.records] == [[[n]] for n in range(7, 13)]


def test_a_model_that_fails_gives_an_error_with_no_question_text(seeded):
    question = "Show me Henry's shots."
    model = ScriptedModel(replies=[ConnectionError(f"cannot send: {question}")])

    with pytest.raises(agent.AgentError) as error:
        agent.ask(agent.build_agent(model), question, "t1")

    assert str(error.value) == "The model call failed (ConnectionError)."
    assert isinstance(error.value.__cause__, ConnectionError)


def test_a_turn_that_ends_with_no_structured_answer_fails(seeded):
    model = ScriptedModel(replies=[answer(), AIMessage(content="Henry was very good.")])
    analyst = agent.build_agent(model)
    agent.ask(analyst, "Show me Henry's shots.", "t1")

    with pytest.raises(agent.AgentError) as error:
        agent.ask(analyst, "And was he good?", "t1")

    assert str(error.value) == "The model gave no structured answer."


def test_no_agent_is_built_when_the_database_cannot_be_read(no_database):
    with pytest.raises(agent.AgentError) as error:
        agent.build_agent(ScriptedModel(replies=[]))

    assert str(error.value) == "The database is not reachable."


def test_the_model_comes_from_the_environment(seeded, analyst_model):
    analyst_model("no_such_provider:some-model")

    with pytest.raises(agent.AgentError) as error:
        agent.build_agent()

    assert str(error.value) == (
        "The model of ANALYST_MODEL (no_such_provider:some-model) did not load (ValueError)."
    )


def test_no_model_name_is_a_settings_error(seeded, analyst_model):
    analyst_model(None)

    with pytest.raises(SettingsError):
        agent.build_agent()


def test_a_model_that_never_gives_a_valid_answer_is_stopped(seeded):
    assert agent.MODEL_CALL_LIMIT == 15
    model = ScriptedModel(replies=[answer(status="not a status") for _ in range(20)])

    with pytest.raises(agent.AgentError) as error:
        agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert str(error.value) == "The question needed more than 15 model calls."
    assert len(model.seen) == 15


def test_the_answer_does_not_count_as_a_tool_call(seeded):
    model = ScriptedModel(replies=[*(query(number) for number in range(1, 11)), answer()])

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert len(turn.records) == 10


def test_a_reply_with_a_tool_call_and_the_answer_keeps_the_record(seeded):
    model = ScriptedModel(
        replies=[calls(("run_sql", {"sql": "SELECT 1 AS n"}), ("Answer", ANSWER)), answer()]
    )

    turn = agent.ask(agent.build_agent(model), "Show me Henry's shots.", "t1")

    assert turn.answer == Answer(**ANSWER)
    assert [record.result["rows"] for record in turn.records] == [[[1]]]


def test_no_agent_is_built_when_the_schema_cannot_be_read(seeded, monkeypatch):
    monkeypatch.setattr(
        agent.tools, "get_schema", lambda: agent.tools.SchemaResult(error="The query failed.")
    )

    with pytest.raises(agent.AgentError) as error:
        agent.build_agent(ScriptedModel(replies=[]))

    assert str(error.value) == "The query failed."


def test_a_tool_description_is_the_docstring_with_no_code_indent():
    by_name = {tool.name: tool for tool in agent.AGENT_TOOLS}

    assert list(by_name) == [
        "get_data_catalog",
        "get_schema",
        "resolve_player",
        "run_sql",
        "build_chart",
    ]
    assert by_name["build_chart"].description.startswith(
        "Build a chart from the rows of one SELECT. The chart holds its data.\n\n"
        "The SQL has the rules of run_sql."
    )
    assert "\n    " not in by_name["resolve_player"].description
