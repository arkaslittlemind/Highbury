"""The analyst over HTTP: a question in, the turn out as server-sent events."""

import json
import logging
import math
import queue
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, JsonValue, StringConstraints
from pydantic_core import to_json
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from analyst import agent
from analyst.answer import Answer, ToolRecord
from analyst.settings import ApiSettings, api_settings
from analyst.verifier import Verification

logger = logging.getLogger(__name__)

# The questions of the chips. The service keeps the answer of each one.
SUGGESTIONS = (
    "Show me Thierry Henry's shots in 2003-04.",
    "Compare Henry in 2003-04 with Saka in 2025-26 on goals and xG per 90.",
    "Show Saka's pass map from 2025-26.",
)

# What a visitor reads while a tool runs.
STEP_LABELS = {
    "get_data_catalog": "Checking what data is available",
    "get_schema": "Reading the data layout",
    "resolve_player": "Finding the player",
    "run_sql": "Querying the match data",
    "build_chart": "Drawing the chart",
}
# A model can call a tool that does not exist. The agent gives it an error.
OTHER_STEP_LABEL = "Working"

# The question goes to a paid model, so its length has a limit.
MAX_QUESTION_LENGTH = 500

# The largest valid body is about 6 KB: a question of 500 characters, where JSON
# can write one character as 12 bytes, plus the conversation id and the keys.
MAX_BODY_BYTES = 16 * 1024

# Each conversation holds the rows of its queries, and the service is public.
MAX_CONVERSATIONS = 200

# The rate limit counts the requests of an address in any window of this length.
WINDOW_SECONDS = 60
# The key of a request with no client address.
NO_ADDRESS = "unknown"

UNEXPECTED = "Something went wrong. Try again."
ENDED = "This conversation has ended. Start a new one."
BUSY = "This conversation is busy. Wait for its answer."
TOO_LARGE = "The request body is too large."


class AskRequest(BaseModel):
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH),
    ]
    # The id that an answer event gave. With no id, the question starts a conversation.
    conversation_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")] | None = None


class StepData(BaseModel):
    number: int
    tool: str
    label: str


class WorkingStep(BaseModel):
    """One tool call of the turn, with no rows and no chart data."""

    tool: str
    args: dict[str, JsonValue]
    # The statement that ran. The argument of the model when the guard refused it.
    sql: str | None
    row_count: int | None
    error: str | None


class AnswerData(BaseModel):
    conversation_id: str
    cached: bool
    answer: Answer
    verification: Verification
    working: list[WorkingStep]


class ErrorData(BaseModel):
    message: str


def show_log() -> None:
    """Make the lines of this module reach stderr."""
    # With no setup, Python drops a line below WARNING, and uvicorn sets up only
    # its own loggers.
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
        logger.addHandler(handler)


def sse(name: str, data: Any) -> str:
    """Return one server-sent event with its data as JSON on one line."""
    # NaN is not JSON, and a browser cannot parse it. It goes out as null.
    return f"event: {name}\ndata: {to_json(data, inf_nan_mode='null').decode()}\n\n"


def working_step(record: ToolRecord) -> WorkingStep:
    result = record.result
    # The arguments come from the model, so a value can have any JSON type.
    sql = result.get("sql") or record.args.get("sql")
    row_count, error = result.get("row_count"), result.get("error")
    return WorkingStep(
        tool=record.name,
        args=record.args,
        sql=sql if isinstance(sql, str) else None,
        row_count=row_count if isinstance(row_count, int) else None,
        error=error if isinstance(error, str) else None,
    )


def answer_data(turn: agent.Turn, conversation_id: str) -> AnswerData:
    return AnswerData(
        conversation_id=conversation_id,
        cached=False,
        answer=turn.answer,
        verification=turn.verification,
        working=[working_step(record) for record in turn.records],
    )


class BodyLimit:
    """Stops the read of a request body at the limit.

    Without it the service reads a body of any size before it checks the
    question, so one request can fill the memory of the process. It is a plain
    ASGI middleware: it changes only what the app reads, and the response stays
    a stream.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        seen = 0

        async def counted() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    # The body reader of FastAPI lets this error through, and
                    # the app answers with it. Any other error becomes a 400.
                    raise HTTPException(413, TOO_LARGE)
            return message

        await self.app(scope, counted, send)


class RateLimiter:
    """A limit on the requests of one address in any 60 seconds."""

    def __init__(self, limit: int, clock: Callable[[], float]) -> None:
        self.limit = limit
        self.clock = clock
        # The times of the counted requests of the last 60 seconds, by address.
        self.times: dict[str, deque[float]] = {}
        self.lock = threading.Lock()

    def wait(self, address: str) -> int:
        """Count a request and return 0, or return the seconds to wait and do not count it."""
        now = self.clock()
        oldest = now - WINDOW_SECONDS
        with self.lock:
            # Each visitor adds an address, so one that is out of the window goes.
            for idle in [known for known, times in self.times.items() if times[-1] <= oldest]:
                del self.times[idle]
            times = self.times.setdefault(address, deque())
            while times and times[0] <= oldest:
                times.popleft()
            if len(times) < self.limit:
                times.append(now)
                return 0
            return max(1, math.ceil(times[0] - oldest))


class UnknownConversation(Exception):
    pass


class BusyConversation(Exception):
    pass


class Conversations:
    """The conversations that the service knows. Each one is a thread of the agent."""

    def __init__(self, limit: int, delete_thread: Callable[[str], None]) -> None:
        self.limit = limit
        self.delete_thread = delete_thread
        # The id, and whether a turn is in flight. The order is the order of last use.
        self.known: OrderedDict[str, bool] = OrderedDict()
        self.lock = threading.Lock()

    def begin(self, conversation_id: str | None) -> str:
        """Mark a turn in flight and return its conversation. No id starts a conversation."""
        dropped: list[str] = []
        with self.lock:
            if conversation_id is None:
                # The service makes the id, so a client cannot name the thread of another.
                conversation_id = uuid.uuid4().hex
                dropped = self.make_room()
            elif conversation_id not in self.known:
                raise UnknownConversation
            elif self.known[conversation_id]:
                raise BusyConversation
            self.known[conversation_id] = True
            self.known.move_to_end(conversation_id)
        for old in dropped:
            self.delete_thread(old)
        return conversation_id

    def make_room(self) -> list[str]:
        """Forget the conversations of the oldest use, so that one more fits."""
        # A conversation with a turn in flight stays: its thread is in use.
        idle = [known for known, in_flight in self.known.items() if not in_flight]
        dropped = idle[: max(0, len(self.known) + 1 - self.limit)]
        for old in dropped:
            del self.known[old]
        return dropped

    def end(self, conversation_id: str, keep: bool) -> None:
        """Mark the turn as ended. A conversation that is not kept is forgotten."""
        with self.lock:
            if keep:
                self.known[conversation_id] = False
            else:
                del self.known[conversation_id]
        if not keep:
            self.delete_thread(conversation_id)


def thread(conversation_id: str) -> dict[str, dict[str, str]]:
    """Return the config that names the thread of a conversation to the agent."""
    return {"configurable": {"thread_id": conversation_id}}


@dataclass
class KeptTurn:
    """The finished turn of a suggestion. The next visitor who asks it waits for no model."""

    # The step and chart events, as they went out.
    events: list[str]
    answer: AnswerData
    # The messages of the conversation after the turn. A follow-up to a kept
    # answer needs them in its own thread.
    messages: list[AnyMessage]


@dataclass
class TurnEnd:
    """How a turn ended."""

    # The answer event or the error event.
    event: str
    # The status of the answer, or "error".
    outcome: str
    cached: bool = False
    tool_calls: int = 0
    usage: agent.Usage = field(default_factory=agent.Usage)


class Service:
    """What the routes share between requests."""

    def __init__(
        self,
        graph: CompiledStateGraph,
        settings: ApiSettings,
        clock: Callable[[], float],
        max_conversations: int,
    ) -> None:
        self.graph = graph
        self.settings = settings
        self.clock = clock
        self.limiter = RateLimiter(settings.rate_limit_per_minute, clock)
        self.conversations = Conversations(max_conversations, graph.checkpointer.delete_thread)
        # The kept turn of each suggestion that a visitor asked. It lives as long
        # as the process: the data changes only when an offline loader runs.
        self.kept: dict[str, KeptTurn] = {}
        self.kept_lock = threading.Lock()

    def run_turn(self, question: str, conversation_id: str, new: bool, events: queue.Queue) -> None:
        """Answer one question on a worker thread. None on the queue ends the stream.

        new says that the question starts its conversation.
        """
        started = self.clock()
        try:
            try:
                end = self.answer(question, conversation_id, new, events.put)
            except Exception as error:
                # A worker thread has no caller to raise to, so this is the last
                # place that can tell the client. The message and the traceback of
                # an error can hold the question, so the log gets only the class.
                logger.error("ask failed: %s", type(error).__name__)
                end = TurnEnd(sse("error", ErrorData(message=UNEXPECTED)), "error")
            # After an error the thread can hold a tool call with no result, so the
            # conversation ends. It is free before the client reads the answer, so
            # that a follow-up that comes at once does not find it busy.
            self.conversations.end(conversation_id, keep=end.outcome != "error")
            events.put(end.event)
            self.log(end, started)
        finally:
            # With no end mark, the stream of the client never ends.
            events.put(None)

    def log(self, end: TurnEnd, started: float) -> None:
        """Write what the turn used. The line holds no text of the visitor or of the model."""
        usage = end.usage
        prices = (self.settings.input_usd_per_mtok, self.settings.output_usd_per_mtok)
        cost = None
        if prices[0] is not None and prices[1] is not None:
            dollars = usage.input_tokens * prices[0] + usage.output_tokens * prices[1]
            cost = round(dollars / 1_000_000, 6)
        line = {
            "event": "ask",
            "outcome": end.outcome,
            "cached": end.cached,
            "latency_ms": round((self.clock() - started) * 1000),
            "model_calls": usage.model_calls,
            "tool_calls": end.tool_calls,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": cost,
        }
        logger.info(json.dumps(line))

    def answer(
        self, question: str, conversation_id: str, new: bool, send: Callable[[str], None]
    ) -> TurnEnd:
        """Send the step and chart events of the turn. Return how it ended."""
        with self.kept_lock:
            # A suggestion that comes as a follow-up needs the model: its answer
            # depends on the turns before it.
            kept = self.kept.get(question) if new else None
        if kept:
            return self.replay(kept, conversation_id, send)
        return self.ask_model(question, conversation_id, new, send)

    def replay(self, kept: KeptTurn, conversation_id: str, send: Callable[[str], None]) -> TurnEnd:
        """Send a kept turn again, in a conversation of its own."""
        for event in kept.events:
            send(event)
        self.graph.update_state(thread(conversation_id), {"messages": kept.messages})
        data = kept.answer.model_copy(update={"conversation_id": conversation_id, "cached": True})
        return TurnEnd(sse("answer", data), data.answer.status, cached=True)

    def compact(self, conversation_id: str) -> list[AnyMessage]:
        """Keep one copy of the messages of the conversation, and return them.

        The checkpointer keeps a full copy of the messages for each step of each
        turn. Without this, the memory of one conversation grows with the square
        of the number of its turns.
        """
        config = thread(conversation_id)
        messages = self.graph.get_state(config).values["messages"]
        self.graph.checkpointer.delete_thread(conversation_id)
        self.graph.update_state(config, {"messages": messages})
        return messages

    def ask_model(
        self, question: str, conversation_id: str, new: bool, send: Callable[[str], None]
    ) -> TurnEnd:
        """Ask the agent. Keep the turn when the question is a suggestion."""
        sent: list[tuple[str, str]] = []
        lock = threading.Lock()

        def emit(name: str, data: Any) -> None:
            event = sse(name, data)
            # The tool calls of one model reply run on more than one thread, and
            # a kept turn must have its events in the order in which they went out.
            with lock:
                sent.append((name, event))
                send(event)

        def on_step(number: int, tool: str) -> None:
            label = STEP_LABELS.get(tool, OTHER_STEP_LABEL)
            emit("step", StepData(number=number, tool=tool, label=label))

        def on_record(record: ToolRecord) -> None:
            chart = record.result.get("chart")
            if record.name == "build_chart" and chart:
                emit("chart", chart)

        try:
            turn = agent.ask(
                self.graph, question, conversation_id, on_step=on_step, on_record=on_record
            )
        except agent.AgentError as error:
            return TurnEnd(
                sse("error", ErrorData(message=str(error))),
                "error",
                tool_calls=sum(name == "step" for name, _ in sent),
                usage=error.usage or agent.Usage(),
            )
        data = answer_data(turn, conversation_id)
        # A tool gives its failure as a result and the model then answers with what
        # it has. A database that was away for one turn must not set the answer
        # that each later visitor gets.
        failed = any(record.result.get("error") for record in turn.records)
        messages = self.compact(conversation_id)
        if new and question in SUGGESTIONS and not failed:
            with self.kept_lock:
                self.kept[question] = KeptTurn([event for _, event in sent], data, messages)
        return TurnEnd(
            sse("answer", data),
            turn.answer.status,
            tool_calls=len(turn.records),
            usage=turn.usage,
        )


def create_app(
    model: BaseChatModel | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    max_conversations: int = MAX_CONVERSATIONS,
) -> FastAPI:
    """Return the app. With no model, the model is the one that ANALYST_MODEL names.

    This is a factory so that an import of the module reads no environment. It
    checks the settings and builds the agent, so a bad environment stops the
    start and not the first question.
    """
    settings = api_settings()
    service = Service(agent.build_agent(model), settings, clock, max_conversations)
    show_log()
    app = FastAPI(title="Highbury analyst")
    app.state.service = service
    # The middleware that is added last is the outer one. CORS must be outside
    # the body limit, or the web page cannot read a 413.
    app.add_middleware(BodyLimit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        # A script of another origin cannot read this header of a 429 without it.
        expose_headers=["Retry-After"],
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_body(request: Request, error: RequestValidationError) -> JSONResponse:
        # The default body repeats the input. The input can be large, and it can
        # hold a character that the response cannot encode, which gives 500.
        detail = [
            {"loc": problem["loc"], "msg": problem["msg"], "type": problem["type"]}
            for problem in error.errors()
        ]
        return JSONResponse({"detail": detail}, status_code=422)

    # The two routes below are async so that they need no thread. Each open
    # stream holds one thread of the pool, and the health path must answer also
    # when the pool is empty.
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        # The app is healthy when the factory ended. A probe reads no database.
        return {"status": "ok"}

    @app.get("/api/suggestions")
    async def suggestions() -> dict[str, list[str]]:
        return {"suggestions": list(SUGGESTIONS)}

    @app.post("/api/ask", response_class=StreamingResponse)
    def ask(body: AskRequest, request: Request) -> StreamingResponse:
        # The address of the connection. A header that the client writes is not
        # a safe key, so a proxy must be set up in uvicorn and not read here.
        address = request.client.host if request.client else NO_ADDRESS
        seconds = service.limiter.wait(address)
        if seconds:
            raise HTTPException(
                429,
                f"Too many questions. Try again in {seconds} seconds.",
                {"Retry-After": str(seconds)},
            )
        try:
            conversation_id = service.conversations.begin(body.conversation_id)
        except UnknownConversation:
            raise HTTPException(404, ENDED) from None
        except BusyConversation:
            raise HTTPException(409, BUSY) from None
        events: queue.Queue[str | None] = queue.Queue()
        # The agent is synchronous. On its own thread, each event leaves when it
        # is made, and the turn ends also when the client goes away.
        new = body.conversation_id is None
        threading.Thread(
            target=service.run_turn,
            args=(body.question, conversation_id, new, events),
            daemon=True,
        ).start()
        return StreamingResponse(
            iter(events.get, None),
            media_type="text/event-stream",
            # A proxy that buffers a response holds each step until the answer
            # is complete. This header tells it to send each event at once.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
