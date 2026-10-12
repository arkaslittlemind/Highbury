import inspect
import json
import logging
import queue
import re
import threading
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from scripted import (
    COUNT_SQL,
    SHOTS_SQL,
    ScriptedModel,
    answer,
    calls,
    shots_claim,
    with_usage,
)

from analyst import api
from analyst.settings import SettingsError

WEB = "http://localhost:3000"
QUESTION = "Show me Henry's shots."
SUGGESTION = "Show me Thierry Henry's shots in 2003-04."
CHART = {"chart_type": "shot_map", "sql": SHOTS_SQL, "title": "Henry"}

Serve = Callable[..., tuple[TestClient, ScriptedModel]]


@pytest.fixture
def serve(seeded, api_env) -> Serve:
    """Start the app with a scripted model. Return the client and the model."""

    def start(
        *replies, limit: int = 1000, prices: tuple[str, str] | None = None, **options
    ) -> tuple[TestClient, ScriptedModel]:
        input_price, output_price = prices or (None, None)
        api_env(
            # A test asks many times in one second, so the limit is high by default.
            RATE_LIMIT_PER_MINUTE=str(limit),
            ANALYST_INPUT_USD_PER_MTOK=input_price,
            ANALYST_OUTPUT_USD_PER_MTOK=output_price,
        )
        model = ScriptedModel(replies=list(replies))
        return TestClient(api.create_app(model, **options)), model

    return start


def not_json(constant: str):
    raise AssertionError(f"{constant} is not JSON")


def events(response: Any) -> list[tuple[str, dict]]:
    """The events of a stream: the name and the data of each one."""
    found = []
    for block in response.text.removesuffix("\n\n").split("\n\n"):
        name, data = block.split("\n")
        assert name.startswith("event: ") and data.startswith("data: ")
        # json.loads reads NaN, which a browser does not.
        found.append((name[7:], json.loads(data[6:], parse_constant=not_json)))
    return found


def ask(client: TestClient, question: str = QUESTION, **more) -> Any:
    return client.post("/api/ask", json={"question": question, **more})


def conversation(response: Any) -> str:
    """The conversation id that the answer event of a stream gave."""
    name, data = events(response)[-1]
    assert name == "answer"
    return data["conversation_id"]


def humans(model: ScriptedModel) -> list[str]:
    """The questions that the model read in its last call."""
    return [message.content for message in model.seen[-1] if message.type == "human"]


def test_the_health_path_says_ok(serve):
    client, _ = serve()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_suggestions_are_the_three_demo_questions(serve):
    client, _ = serve()

    response = client.get("/api/suggestions")

    assert response.status_code == 200
    assert response.json() == {
        "suggestions": [
            "Show me Thierry Henry's shots in 2003-04.",
            "Compare Henry in 2003-04 with Saka in 2025-26 on goals and xG per 90.",
            "Show Saka's pass map from 2025-26.",
        ]
    }


def test_a_request_from_the_web_origin_is_allowed(serve):
    client, _ = serve()

    response = client.get("/api/health", headers={"Origin": WEB})

    assert response.headers["access-control-allow-origin"] == WEB


def test_a_request_from_another_origin_gets_no_cors_header(serve):
    client, _ = serve()

    response = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(("origin", "status"), [(WEB, 200), ("http://evil.example", 400)])
def test_the_browser_can_ask_first_if_it_can_post_json(serve, origin, status):
    client, _ = serve()

    response = client.options(
        "/api/ask",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == status


def test_the_app_does_not_start_with_a_bad_environment(seeded, api_env):
    api_env(RATE_LIMIT_PER_MINUTE=None)

    with pytest.raises(SettingsError) as error:
        api.create_app(ScriptedModel(replies=[]))

    assert str(error.value) == "RATE_LIMIT_PER_MINUTE is not set"


def test_the_app_does_not_start_when_the_database_cannot_be_read(no_database, api_env):
    api_env()

    with pytest.raises(api.agent.AgentError) as error:
        api.create_app(ScriptedModel(replies=[]))

    assert str(error.value) == "The database is not reachable."


def test_a_turn_streams_its_steps_and_its_chart_before_its_answer(serve):
    client, _ = serve(
        calls(("run_sql", {"sql": COUNT_SQL})),
        calls(("build_chart", CHART)),
        lambda read: answer(
            claims=[shots_claim(read["run_sql"]["call_id"]), shots_claim("q_none")],
            charts=[{"id": read["build_chart"]["chart"]["id"]}],
        ),
    )

    response = ask(client)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    (_, first), (_, second), (_, chart), (_, last) = found = events(response)
    assert [name for name, _ in found] == ["step", "step", "chart", "answer"]
    assert first == {"number": 1, "tool": "run_sql", "label": "Querying the match data"}
    assert second == {"number": 2, "tool": "build_chart", "label": "Drawing the chart"}
    assert chart["type"] == "shot_map"
    assert chart["title"] == "Henry"
    assert len(chart["shots"]) == 2
    assert re.fullmatch(r"[0-9a-f]{32}", last["conversation_id"])
    assert last["cached"] is False
    query_id = last["answer"]["claims"][0]["tool_call_id"]
    assert re.fullmatch(r"q_[0-9a-f]{8}", query_id)
    assert last["answer"] == {
        "status": "answered",
        "summary": "Thierry Henry took 2 shots in 2003-04.",
        "claims": [shots_claim(query_id)],
        "charts": [{"id": chart["id"]}],
        "caveats": [],
        "alternative": None,
    }
    assert last["verification"] == {
        "checked": 2,
        "passed": 1,
        "removed": [{"claim": shots_claim("q_none"), "reason": "call_not_found"}],
        "unbacked_numbers": [],
    }
    query, drawn = last["working"]
    assert query["sql"].startswith("SELECT COUNT(*) AS shots FROM v_shots")
    assert query == {
        "tool": "run_sql",
        "args": {"sql": COUNT_SQL},
        "sql": query["sql"],
        "row_count": 1,
        "error": None,
    }
    assert (drawn["tool"], drawn["args"], drawn["row_count"]) == ("build_chart", CHART, 2)


def test_the_claim_of_the_answer_cites_the_query_of_the_turn(serve):
    client, _ = serve(
        calls(("run_sql", {"sql": COUNT_SQL})),
        lambda read: answer(claims=[shots_claim(read["run_sql"]["call_id"])]),
    )

    (_, step), (_, last) = events(ask(client))

    assert step["tool"] == "run_sql"
    (claim,) = last["answer"]["claims"]
    assert re.fullmatch(r"q_[0-9a-f]{8}", claim["tool_call_id"])
    assert last["verification"]["passed"] == 1


def test_the_working_holds_no_rows_and_no_chart_data(serve):
    client, _ = serve(
        calls(("run_sql", {"sql": COUNT_SQL}), ("build_chart", CHART)),
        calls(("run_sql", {"statement": "SELECT 1"})),
        calls(("run_sql", {"sql": "DELETE FROM shots"})),
        answer(),
    )

    *_, (_, last) = events(ask(client))

    assert [set(step) for step in last["working"]] == [
        {"tool", "args", "sql", "row_count", "error"}
    ] * 4
    wrong_arguments, refused = last["working"][2:]
    assert (wrong_arguments["sql"], wrong_arguments["row_count"]) == (None, None)
    assert "sql" in wrong_arguments["error"]
    # The guard gives no statement back, so the working shows what the model sent.
    assert refused["sql"] == "DELETE FROM shots"
    assert refused["error"]


def test_a_tool_that_does_not_exist_has_the_other_label(serve):
    client, _ = serve(calls(("guess_the_score", {})), answer())

    (_, step), _ = events(ask(client))

    assert step == {"number": 1, "tool": "guess_the_score", "label": "Working"}


def test_a_turn_with_no_tool_call_streams_only_its_answer(serve):
    client, _ = serve(answer(status="out_of_scope", summary="I only cover Arsenal."))

    ((name, last),) = events(ask(client, "Who will win the Champions League?"))

    assert name == "answer"
    assert last["answer"]["status"] == "out_of_scope"
    assert last["working"] == []


def test_a_turn_that_fails_streams_the_safe_text_of_its_error(serve):
    client, _ = serve(calls(("run_sql", {"sql": COUNT_SQL})), ConnectionError(f"sent: {QUESTION}"))

    response = ask(client)

    assert response.status_code == 200
    assert events(response)[1:] == [
        ("error", {"message": "The model call failed (ConnectionError)."})
    ]


def test_an_error_that_nobody_expected_streams_a_text_with_no_detail(serve, monkeypatch, caplog):
    client, _ = serve()

    def broken(*args, **kwargs):
        raise RuntimeError(f"cannot answer: {QUESTION}")

    monkeypatch.setattr(api.agent, "ask", broken)

    response = ask(client)

    assert events(response) == [("error", {"message": "Something went wrong. Try again."})]
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert errors == ["ask failed: RuntimeError"]
    assert QUESTION not in caplog.text


def test_a_number_that_is_not_finite_goes_out_as_null(serve):
    lost = {**shots_claim("q_none"), "value": float("nan")}
    client, _ = serve(answer(claims=[lost]))

    ((_, last),) = events(ask(client))

    (removed,) = last["verification"]["removed"]
    assert removed["claim"]["value"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 501},
        {"question": 7},
        {},
    ],
)
def test_a_question_that_is_not_valid_gets_422_and_no_model_call(serve, body):
    client, model = serve(answer())

    response = client.post("/api/ask", json=body)

    assert response.status_code == 422
    assert model.seen == []


def test_a_question_of_500_characters_is_valid_and_loses_the_space_at_its_ends(serve):
    client, model = serve(answer())

    response = ask(client, "  " + "x" * 500 + "\n")

    assert response.status_code == 200
    assert model.seen[0][-1].content == "x" * 500


def test_a_follow_up_reads_the_turn_before_it(serve):
    client, model = serve(answer(), answer(), answer())
    first = conversation(ask(client))

    follow_up = ask(client, "Only the ones inside the box.", conversation_id=first)

    assert conversation(follow_up) == first
    assert humans(model) == [QUESTION, "Only the ones inside the box."]
    # A question with no id starts a conversation of its own.
    assert conversation(ask(client, "And Saka?")) != first
    assert humans(model) == ["And Saka?"]


def test_a_conversation_keeps_one_copy_of_its_messages(serve):
    def turn(number: int) -> list:
        return [calls(("run_sql", {"sql": f"SELECT {number} AS n"})), answer()]

    client, model = serve(*turn(1), *turn(2), *turn(3))
    saver = client.app.state.service.graph.checkpointer

    def checkpoints(conversation_id: str) -> int:
        return len(list(saver.list({"configurable": {"thread_id": conversation_id}})))

    first = conversation(ask(client, "One?"))
    after_one_turn = checkpoints(first)
    ask(client, "Two?", conversation_id=first)
    ask(client, "Three?", conversation_id=first)

    # Each step of a turn is a checkpoint with a full copy of the messages.
    assert checkpoints(first) == after_one_turn == 1
    # The first model call of the third turn still read the two turns before it.
    third_turn = model.seen[4]
    assert [m.content for m in third_turn if m.type == "human"] == ["One?", "Two?", "Three?"]
    queries = [json.loads(m.content)["rows"] for m in third_turn if m.name == "run_sql"]
    assert queries == [[[1]], [[2]]]


def test_a_conversation_that_the_service_does_not_know_gets_404(serve):
    client, model = serve(answer())

    response = ask(client, conversation_id="0" * 32)

    assert response.status_code == 404
    assert response.json() == {"detail": "This conversation has ended. Start a new one."}
    assert model.seen == []


@pytest.mark.parametrize("wrong", ["A" * 32, "0" * 31, "0" * 33, "g" * 32, "t1", "", 7])
def test_a_conversation_id_of_a_wrong_form_gets_422(serve, wrong):
    client, _ = serve(answer())

    assert ask(client, conversation_id=wrong).status_code == 422


def test_a_null_conversation_id_starts_a_conversation(serve):
    client, _ = serve(answer())

    assert conversation(ask(client, conversation_id=None))


def test_a_conversation_with_a_turn_in_flight_gets_409(serve):
    started, release = threading.Event(), threading.Event()

    def slow(read):
        started.set()
        assert release.wait(10)
        return answer()

    client, _ = serve(answer(), slow, answer())
    first = conversation(ask(client))
    responses = []
    in_flight = threading.Thread(
        target=lambda: responses.append(ask(TestClient(client.app), conversation_id=first))
    )
    in_flight.start()
    assert started.wait(10)

    busy = ask(client, conversation_id=first)

    release.set()
    in_flight.join(10)
    assert busy.status_code == 409
    assert busy.json() == {"detail": "This conversation is busy. Wait for its answer."}
    assert conversation(responses[0]) == first
    # The conversation is free again when its answer is out.
    assert ask(client, conversation_id=first).status_code == 200


def test_a_conversation_ends_when_a_turn_fails(serve):
    client, _ = serve(answer(), ConnectionError("no route"))
    first = conversation(ask(client))
    graph = client.app.state.service.graph
    thread = {"configurable": {"thread_id": first}}
    assert graph.get_state(thread).values

    failed = ask(client, conversation_id=first)

    assert events(failed)[-1][0] == "error"
    assert ask(client, conversation_id=first).status_code == 404
    # The thread can hold a tool call with no result, so it is gone too.
    assert graph.get_state(thread).values == {}


def test_a_new_conversation_that_fails_is_not_kept(serve):
    client, _ = serve(ConnectionError("no route"))

    ask(client)

    assert client.app.state.service.conversations.known == {}


def test_the_conversation_of_the_oldest_use_goes_when_the_limit_is_reached(serve):
    client, _ = serve(*(answer() for _ in range(6)), max_conversations=2)
    first = conversation(ask(client))
    second = conversation(ask(client))
    # A use makes the first one newer than the second one.
    assert ask(client, conversation_id=first).status_code == 200

    third = conversation(ask(client))

    assert ask(client, conversation_id=second).status_code == 404
    assert ask(client, conversation_id=first).status_code == 200
    assert ask(client, conversation_id=third).status_code == 200
    graph = client.app.state.service.graph
    assert graph.get_state({"configurable": {"thread_id": second}}).values == {}


def test_a_conversation_with_a_turn_in_flight_is_not_forgotten():
    deleted = []
    conversations = api.Conversations(1, deleted.append)
    first = conversations.begin(None)

    second = conversations.begin(None)

    assert list(conversations.known) == [first, second]
    conversations.end(first, keep=True)
    conversations.end(second, keep=True)
    third = conversations.begin(None)
    assert list(conversations.known) == [third]
    assert deleted == [first, second]


class Clock:
    """A clock that a test moves."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_limiter_lets_the_limit_through_in_any_60_seconds():
    clock = Clock()
    limiter = api.RateLimiter(5, clock)
    waits = []
    for second in (0, 10, 20, 30, 40):
        clock.now = 1000.0 + second
        waits.append(limiter.wait("1.1.1.1"))
    assert waits == [0, 0, 0, 0, 0]

    clock.now = 1045.5
    assert limiter.wait("1.1.1.1") == 15
    # A request that the limiter refused does not count.
    clock.now = 1059.9
    assert limiter.wait("1.1.1.1") == 1
    # The oldest request is 60 seconds old now.
    clock.now = 1060.0
    assert limiter.wait("1.1.1.1") == 0
    assert limiter.wait("1.1.1.1") == 10


def test_each_address_has_its_own_count():
    limiter = api.RateLimiter(1, Clock())

    assert limiter.wait("1.1.1.1") == 0
    assert limiter.wait("2.2.2.2") == 0
    assert limiter.wait("1.1.1.1") == 60


def test_an_address_with_no_request_in_the_window_holds_no_memory():
    clock = Clock()
    limiter = api.RateLimiter(5, clock)
    limiter.wait("1.1.1.1")
    clock.now += 30
    limiter.wait("2.2.2.2")

    clock.now += 30
    limiter.wait("3.3.3.3")

    assert list(limiter.times) == ["2.2.2.2", "3.3.3.3"]


def test_the_sixth_question_of_a_minute_gets_429(serve):
    clock = Clock()
    client, model = serve(*(answer() for _ in range(6)), limit=5, clock=clock)
    # A body that is not valid does not count.
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    for second in range(5):
        clock.now = 1000.0 + second
        assert ask(client).status_code == 200

    refused = ask(client)

    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "56"
    assert refused.json() == {"detail": "Too many questions. Try again in 56 seconds."}
    assert len(model.seen) == 5
    clock.now = 1060.0
    assert ask(client).status_code == 200


def test_a_question_that_gets_404_counts(serve):
    client, _ = serve(limit=2)

    statuses = [ask(client, conversation_id="0" * 32).status_code for _ in range(3)]

    assert statuses == [404, 404, 429]


def test_the_limit_is_for_each_address(serve):
    client, _ = serve(answer(), answer(), limit=1)
    other = TestClient(client.app, client=("10.0.0.2", 50000))

    assert ask(client).status_code == 200
    assert ask(other).status_code == 200
    assert ask(client).status_code == 429
    assert ask(other).status_code == 429


def suggestion_turn() -> list:
    """The replies of a turn with a query, a chart, and a claim."""
    return [
        calls(("run_sql", {"sql": COUNT_SQL})),
        calls(("build_chart", CHART)),
        lambda read: answer(claims=[shots_claim(read["run_sql"]["call_id"])]),
    ]


def test_the_second_visitor_gets_the_kept_turn_of_a_suggestion_with_no_model_call(serve):
    client, model = serve(*suggestion_turn(), answer())
    *first_events, (_, first) = events(ask(client, SUGGESTION))

    *second_events, (_, second) = events(ask(client, f"  {SUGGESTION}\n"))

    assert len(model.seen) == 3
    assert [name for name, _ in second_events] == ["step", "step", "chart"]
    assert second_events == first_events
    assert (first["cached"], second["cached"]) == (False, True)
    assert second["conversation_id"] != first["conversation_id"]
    changed = ("cached", "conversation_id")
    assert {key: value for key, value in second.items() if key not in changed} == {
        key: value for key, value in first.items() if key not in changed
    }
    assert second["verification"]["passed"] == 1


def test_a_follow_up_to_a_kept_answer_reads_the_kept_turn(serve):
    client, model = serve(*suggestion_turn(), answer(), answer())
    first = conversation(ask(client, SUGGESTION))
    kept = conversation(ask(client, SUGGESTION))

    follow_up = ask(client, "Only the ones inside the box.", conversation_id=kept)

    assert conversation(follow_up) == kept
    assert humans(model) == [SUGGESTION, "Only the ones inside the box."]
    # The model reads the tool calls of the kept turn, not only its question.
    assert [message.type for message in model.seen[-1]] == [
        "system",
        "human",
        "ai",
        "tool",
        "ai",
        "tool",
        "ai",
        "tool",
        "human",
    ]
    # The conversation of the first visitor has no part of that follow-up.
    ask(client, "And how many goals?", conversation_id=first)
    assert humans(model) == [SUGGESTION, "And how many goals?"]


def test_each_status_of_a_suggestion_is_kept(serve):
    no_passes = "Show Saka's pass map from 2025-26."
    client, model = serve(answer(status="unavailable", alternative="His shot map."))
    ask(client, no_passes)

    ((_, second),) = events(ask(client, no_passes))

    assert second["cached"] is True
    assert second["answer"]["status"] == "unavailable"
    assert len(model.seen) == 1


def test_a_suggestion_turn_with_a_failed_tool_call_is_not_kept(serve):
    client, model = serve(
        calls(("run_sql", {"sql": "DELETE FROM shots"})),
        answer(status="unavailable", summary="I cannot read the shots now."),
        answer(),
    )
    *_, (_, first) = events(ask(client, SUGGESTION))
    assert first["working"][0]["error"]

    ((_, second),) = events(ask(client, SUGGESTION))

    # The answer of a turn with a tool error can be wrong for the next visitor.
    assert second["cached"] is False
    assert second["answer"]["status"] == "answered"
    assert len(model.seen) == 3
    assert client.app.state.service.kept[SUGGESTION].answer.answer.status == "answered"


def test_a_suggestion_turn_that_fails_is_not_kept(serve):
    client, model = serve(ConnectionError("no route"), answer())
    assert events(ask(client, SUGGESTION))[-1][0] == "error"

    ((_, second),) = events(ask(client, SUGGESTION))

    assert second["cached"] is False
    assert len(model.seen) == 2


def test_a_question_that_is_not_a_suggestion_is_not_kept(serve):
    client, model = serve(answer(), answer())
    ask(client)

    ((_, second),) = events(ask(client))

    assert second["cached"] is False
    assert len(model.seen) == 2
    assert client.app.state.service.kept == {}


def test_a_suggestion_that_comes_as_a_follow_up_reaches_the_model(serve):
    client, model = serve(answer(), answer(summary="Still 2 shots."), answer())
    first = conversation(ask(client, SUGGESTION))

    ((_, follow_up),) = events(ask(client, SUGGESTION, conversation_id=first))

    assert follow_up["cached"] is False
    assert len(model.seen) == 2
    assert humans(model) == [SUGGESTION, SUGGESTION]
    # The answer of a follow-up depends on its conversation, so it is not kept.
    ((_, later),) = events(ask(client, SUGGESTION))
    assert later["cached"] is True
    assert later["answer"]["summary"] == "Thierry Henry took 2 shots in 2003-04."


def log_lines(caplog) -> list[dict]:
    """The lines that the API wrote about its turns."""
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "analyst.api" and record.levelno == logging.INFO
    ]


def test_a_turn_writes_one_line_with_what_it_used(serve, caplog):
    clock = Clock()

    def last(read):
        clock.now += 1.5
        return with_usage(answer(), 2000, 300)

    client, _ = serve(
        with_usage(calls(("run_sql", {"sql": COUNT_SQL})), 1000, 20),
        last,
        prices=("0.30", "2.50"),
        clock=clock,
    )

    ask(client)

    assert log_lines(caplog) == [
        {
            "event": "ask",
            "outcome": "answered",
            "cached": False,
            "latency_ms": 1500,
            "model_calls": 2,
            "tool_calls": 1,
            "input_tokens": 3000,
            "output_tokens": 320,
            # (3000 * 0.30 + 320 * 2.50) / 1,000,000
            "cost_usd": 0.0017,
        }
    ]


def test_the_line_has_no_cost_when_the_prices_are_not_set(serve, caplog):
    client, _ = serve(with_usage(answer(status="out_of_scope"), 1000, 20))

    ask(client)

    (line,) = log_lines(caplog)
    assert line["cost_usd"] is None
    assert (line["outcome"], line["input_tokens"], line["output_tokens"]) == (
        "out_of_scope",
        1000,
        20,
    )


def test_a_kept_turn_writes_a_line_with_no_tokens(serve, caplog):
    client, _ = serve(with_usage(answer(), 1000, 20), prices=("0.30", "2.50"))
    ask(client, SUGGESTION)

    ask(client, SUGGESTION)

    _, kept = log_lines(caplog)
    assert kept == {
        "event": "ask",
        "outcome": "answered",
        "cached": True,
        "latency_ms": kept["latency_ms"],
        "model_calls": 0,
        "tool_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }


def test_a_turn_that_fails_writes_what_it_used_before_the_error(serve, caplog):
    client, _ = serve(
        with_usage(calls(("run_sql", {"sql": COUNT_SQL})), 1000, 20), ConnectionError("no route")
    )

    ask(client)

    (line,) = log_lines(caplog)
    assert (line["outcome"], line["model_calls"], line["tool_calls"]) == ("error", 2, 1)
    assert (line["input_tokens"], line["output_tokens"]) == (1000, 20)


def test_an_error_that_nobody_expected_writes_a_line_too(serve, monkeypatch, caplog):
    client, _ = serve()
    monkeypatch.setattr(api.agent, "ask", lambda *args, **kwargs: 1 / 0)

    ask(client)

    (line,) = log_lines(caplog)
    assert (line["outcome"], line["model_calls"]) == ("error", 0)


def test_the_log_holds_no_text_of_the_turn(serve, caplog):
    question = "How many shots did Titi take?"
    sql = "SELECT count(*) AS titi_shots FROM v_shots"
    client, _ = serve(
        calls(("run_sql", {"sql": sql})),
        lambda read: answer(
            summary="Titi took 2 shots.",
            claims=[{**shots_claim(read["run_sql"]["call_id"]), "text": "Two for Titi"}],
        ),
    )
    caplog.set_level(logging.DEBUG)

    first = conversation(ask(client, question))

    ours = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("analyst"))
    assert ours.startswith('{"event": "ask"')
    for text in ("Titi", "titi_shots", "SELECT", "testclient", first):
        assert text not in ours


def test_a_request_that_gets_no_stream_writes_no_line(serve, caplog):
    client, _ = serve(limit=2)

    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert ask(client, conversation_id="0" * 32).status_code == 404
    assert ask(client, conversation_id="0" * 32).status_code == 404
    assert ask(client).status_code == 429

    assert log_lines(caplog) == []


def test_the_app_shows_its_log_lines_one_time(serve):
    serve()
    serve()

    logger = logging.getLogger("analyst.api")
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1


def test_the_web_page_can_read_the_wait_of_a_429(serve):
    client, _ = serve(answer(), limit=1)
    ask(client)

    refused = client.post("/api/ask", json={"question": QUESTION}, headers={"Origin": WEB})

    assert refused.status_code == 429
    assert refused.headers["retry-after"] == "60"
    assert refused.headers["access-control-allow-origin"] == WEB
    assert refused.headers["access-control-expose-headers"] == "Retry-After"


@pytest.mark.parametrize(
    "body",
    [
        b'{"question": "\\ud800 shots"}',
        b'{"question": "Shots?", "conversation_id": "\\ud800"}',
    ],
)
def test_a_text_that_json_permits_and_utf8_does_not_gets_422(serve, body):
    client, model = serve(answer())

    response = client.post("/api/ask", content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert model.seen == []


@pytest.mark.parametrize(
    ("body", "loc"),
    [
        ({"question": "x" * 501}, ["body", "question"]),
        ({"question": "Shots?", "conversation_id": "y" * 40}, ["body", "conversation_id"]),
        ({}, ["body", "question"]),
    ],
)
def test_the_body_of_a_422_names_the_field_and_does_not_repeat_the_input(serve, body, loc):
    client, _ = serve()

    response = client.post("/api/ask", json=body)

    assert response.status_code == 422
    (problem,) = response.json()["detail"]
    assert set(problem) == {"loc", "msg", "type"}
    assert problem["loc"] == loc
    assert "xxx" not in response.text
    assert "yyy" not in response.text


def test_a_body_that_is_not_json_gets_422_with_no_input(serve):
    client, _ = serve()

    response = client.post(
        "/api/ask", content=b"Show me the shots", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert "shots" not in response.text


def test_the_routes_that_must_always_answer_need_no_thread(serve):
    client, _ = serve()

    routes = {route.path: route.endpoint for route in client.app.routes}

    # An open stream holds a thread of the pool, and a plain function needs one.
    assert inspect.iscoroutinefunction(routes["/api/health"])
    assert inspect.iscoroutinefunction(routes["/api/suggestions"])


def test_a_turn_ends_as_a_whole_when_nobody_reads_its_events(serve, caplog):
    client, _ = serve(*suggestion_turn())
    service = client.app.state.service
    conversation_id = service.conversations.begin(None)
    # A client that goes away reads no event of its stream.
    unread: queue.Queue = queue.Queue()

    service.run_turn(SUGGESTION, conversation_id, True, unread)

    assert service.conversations.known == {conversation_id: False}
    assert SUGGESTION in service.kept
    (line,) = log_lines(caplog)
    assert (line["outcome"], line["tool_calls"]) == ("answered", 2)


def test_a_step_leaves_while_the_turn_still_runs(serve):
    release = threading.Event()

    def slow(read):
        assert release.wait(10)
        return answer()

    client, _ = serve(calls(("run_sql", {"sql": COUNT_SQL})), slow)
    service = client.app.state.service
    conversation_id = service.conversations.begin(None)
    out: queue.Queue = queue.Queue()
    turn = threading.Thread(target=service.run_turn, args=(QUESTION, conversation_id, True, out))
    turn.start()

    try:
        first = out.get(timeout=10)
        # The model has not given its next reply, so the turn has no answer yet.
        still_running = turn.is_alive() and not release.is_set()
    finally:
        release.set()
        turn.join(10)

    assert first.startswith("event: step\n")
    assert still_running
    assert out.get_nowait().startswith("event: answer\n")
    assert out.get_nowait() is None
