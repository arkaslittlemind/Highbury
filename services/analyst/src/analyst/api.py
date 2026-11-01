"""The analyst over HTTP: a question in, the turn out as server-sent events."""

import json
import logging
import math
import queue
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
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

from analyst import agent, turnstile
from analyst.answer import Answer, ToolRecord
from analyst.settings import ApiSettings, api_settings
from analyst.verifier import Verification

logger = logging.getLogger(__name__)

# The questions of the chips. The service keeps the answer of each one.
SUGGESTIONS = (
    "Show me Thierry Henry's shots in 2003-04.",
    "Compare Henry in 2003-04 with Saka in 2025-26 on goals and xG per 90.",
    "Show Saka's pass map from 2025-26.",
    "Show Arsenal's pass network vs Liverpool at home.",
)

# What a visitor reads while a tool runs.
STEP_LABELS = {
    "resolve_player": "Finding the player",
    "run_sql": "Querying the match data",
    "build_chart": "Drawing the chart",
}
# A model can call a tool that does not exist. The agent gives it an error.
OTHER_STEP_LABEL = "Working"

# The question goes to a paid model, so its length has a limit.
MAX_QUESTION_LENGTH = 500

# Cloudflare gives a token of up to 2048 characters.
MAX_TOKEN_LENGTH = 2048

# The largest valid body is about 8 KB: a question of 500 characters, where JSON
# can write one character as 12 bytes, plus the token, the conversation id and
# the keys.
MAX_BODY_BYTES = 16 * 1024

# Each conversation holds the rows of its queries, and the service is public.
MAX_CONVERSATIONS = 200
# Each turn adds its rows to the memory of its conversation, so the number of
# conversations alone does not bound the memory.
MAX_TURNS = 20

# The rate limit counts the requests of an address in any window of this length.
WINDOW_SECONDS = 60
# The key of a request with no client address.
NO_ADDRESS = "unknown"

# Most of a turn waits on the model, but each turn holds a thread and the rows
# of its queries, and the one task of the service is small.
MAX_ACTIVE_TURNS = 10

UNEXPECTED = "Something went wrong. Try again."
ENDED = "This conversation has ended. Start a new one."
BUSY = "This conversation is busy. Wait for its answer."
TOO_LARGE = "The request body is too large."
ADDRESS_LIMIT = "You have asked {limit} questions today. Come back tomorrow."
SITE_LIMIT = "Highbury has answered all the questions it can today. Come back tomorrow."
SERVICE_BUSY = "Highbury is busy. Try again in a minute."
BOT_CHECK_FAILED = (
    "The bot check did not pass. If you use an ad blocker or privacy extension, "
    "allow challenges.cloudflare.com, then try again."
)
BOT_CHECK_UNAVAILABLE = "The bot check is not available. Try again in a few minutes."

# Asks Cloudflare about a token for an address.
VerifyToken = Callable[[str, str], turnstile.Verdict]


class AskRequest(BaseModel):
    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_LENGTH),
    ]
    # The id that an answer event gave. With no id, the question starts a conversation.
    conversation_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")] | None = None
    # Optional here so that a question with no token gets the 403 that the page
    # can show, and not a 422.
    turnstile_token: Annotated[str, StringConstraints(max_length=MAX_TOKEN_LENGTH)] | None = None


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
    # The id of the query of the call, which a claim cites as tool_call_id.
    # None when the call ran no query.
    call_id: str | None


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


# The load balancer closes a connection that is quiet for 60 seconds, and one
# model call can take longer. The web page skips an event that it does not know.
HEARTBEAT_SECONDS = 15
PING = sse("ping", {})


def stream(events: queue.Queue[str | None]) -> Iterator[str]:
    """Yield the events of a turn until None, and a ping when the turn is quiet."""
    while True:
        try:
            event = events.get(timeout=HEARTBEAT_SECONDS)
        except queue.Empty:
            yield PING
            continue
        if event is None:
            return
        yield event


def working_step(record: ToolRecord) -> WorkingStep:
    result = record.result
    # The arguments come from the model, so a value can have any JSON type.
    sql = result.get("sql") or record.args.get("sql")
    row_count, error = result.get("row_count"), result.get("error")
    call_id = result.get("call_id")
    return WorkingStep(
        tool=record.name,
        args=record.args,
        sql=sql if isinstance(sql, str) else None,
        row_count=row_count if isinstance(row_count, int) else None,
        error=error if isinstance(error, str) else None,
        call_id=call_id if isinstance(call_id, str) else None,
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


def utc_today() -> date:
    return datetime.now(UTC).date()


class DailyLimitReached(Exception):
    """A daily limit refused the question. scope is "address" or "site"."""

    def __init__(self, scope: str) -> None:
        super().__init__(scope)
        self.scope = scope


class DailyLimits:
    """A limit on the paid questions of one address, and of all addresses, in a UTC day.

    The counts live in memory, so they are right only while the service runs one
    task, and a restart or a deploy clears them.
    """

    def __init__(self, per_address: int, total: int, today: Callable[[], date]) -> None:
        self.per_address = per_address
        self.limit = total
        self.today = today
        self.day = today()
        self.by_address: dict[str, int] = {}
        self.total = 0
        self.lock = threading.Lock()

    def take(self, address: str) -> date:
        """Count a question and return the day of the count.

        Raise DailyLimitReached and count nothing when a limit is reached.
        """
        with self.lock:
            today = self.today()
            if today != self.day:
                self.day, self.by_address, self.total = today, {}, 0
            if self.by_address.get(address, 0) >= self.per_address:
                raise DailyLimitReached("address")
            if self.total >= self.limit:
                raise DailyLimitReached("site")
            self.by_address[address] = self.by_address.get(address, 0) + 1
            self.total += 1
            return self.day

    def give_back(self, address: str, day: date) -> None:
        """Take back the count that take made on day, for a question that did not start."""
        with self.lock:
            # After midnight the counts of that day are gone, and a count of the new
            # day belongs to another question.
            if day == self.day and self.by_address.get(address, 0) > 0:
                self.by_address[address] -= 1
                self.total -= 1


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
        # The turns that each known conversation started.
        self.turns: dict[str, int] = {}
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
            self.turns[conversation_id] = self.turns.get(conversation_id, 0) + 1
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
            del self.turns[old]
        return dropped

    def end(self, conversation_id: str, keep: bool) -> None:
        """Mark the turn as ended. A conversation that is not kept is forgotten.

        The last turn that a conversation can have also forgets it, so that its
        memory is free at once. The next question on its id gets the 404 of a
        conversation that ended.
        """
        with self.lock:
            keep = keep and self.turns[conversation_id] < MAX_TURNS
            if keep:
                self.known[conversation_id] = False
            else:
                del self.known[conversation_id]
                del self.turns[conversation_id]
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
        verify_token: VerifyToken,
        today: Callable[[], date] = utc_today,
        max_active_turns: int = MAX_ACTIVE_TURNS,
    ) -> None:
        self.graph = graph
        self.settings = settings
        self.verify_token = verify_token
        self.clock = clock
        self.limiter = RateLimiter(settings.rate_limit_per_minute, clock)
        self.daily = DailyLimits(
            settings.daily_limit_per_address, settings.daily_limit_total, today
        )
        # The turns that call the model now. A kept suggestion takes no slot.
        self.max_active = max_active_turns
        self.active = 0
        self.active_lock = threading.Lock()
        self.conversations = Conversations(max_conversations, graph.checkpointer.delete_thread)
        # The kept turn of each suggestion that a visitor asked. It lives as long
        # as the process: the data changes only when an offline loader runs.
        self.kept: dict[str, KeptTurn] = {}
        self.kept_lock = threading.Lock()

    def take_slot(self) -> bool:
        """Hold a slot for a turn that calls the model, or return False when all are held."""
        with self.active_lock:
            if self.active >= self.max_active:
                return False
            self.active += 1
            return True

    def free_slot(self) -> None:
        with self.active_lock:
            self.active -= 1

    def kept_turn(self, question: str, new: bool) -> "KeptTurn | None":
        """The kept turn that answers the question, or None when the model must answer."""
        with self.kept_lock:
            # A suggestion that comes as a follow-up needs the model: its answer
            # depends on the turns before it.
            return self.kept.get(question) if new else None

    def run_turn(
        self,
        question: str,
        conversation_id: str,
        new: bool,
        events: queue.Queue,
        slot: bool = False,
    ) -> None:
        """Answer one question on a worker thread. None on the queue ends the stream.

        new says that the question starts its conversation, and slot that the
        route took a slot for it.
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
            if slot:
                self.free_slot()
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
        kept = self.kept_turn(question, new)
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
        # The event comes before the kept turn: an answer that cannot be written
        # must not stay as the answer of each later visitor.
        answer_event = sse("answer", data)
        if new and question in SUGGESTIONS and not failed:
            with self.kept_lock:
                self.kept[question] = KeptTurn([event for _, event in sent], data, messages)
        return TurnEnd(
            answer_event,
            turn.answer.status,
            tool_calls=len(turn.records),
            usage=turn.usage,
        )


def create_app(
    model: BaseChatModel | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    max_conversations: int = MAX_CONVERSATIONS,
    today: Callable[[], date] = utc_today,
    max_active_turns: int = MAX_ACTIVE_TURNS,
    verify_token: VerifyToken | None = None,
) -> FastAPI:
    """Return the app. With no model, the model is the one that ANALYST_MODEL names.

    With no verify_token, each token goes to Cloudflare with the secret of the
    settings. A test gives its own, so that it calls no network.

    This is a factory so that an import of the module reads no environment. It
    checks the settings and builds the agent, so a bad environment stops the
    start and not the first question.
    """
    settings = api_settings()
    if verify_token is None:
        client = turnstile.make_client()
        secret = settings.turnstile_secret_key.get_secret_value()

        def verify_token(token: str, address: str) -> turnstile.Verdict:
            return turnstile.verify(client, secret, token, address)

    service = Service(
        agent.build_agent(model),
        settings,
        clock,
        max_conversations,
        verify_token,
        today=today,
        max_active_turns=max_active_turns,
    )
    show_log()
    app = FastAPI(title="Highbury analyst")
    app.state.service = service
    # The body limit sends no response. It raises its error in the route, and
    # the exception handler of the app makes the 413. That handler is inside
    # the two middlewares, so the 413 gets the CORS header in each order.
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
        # After the rate limit, so that a flood is not a flood of calls to
        # Cloudflare. Before the daily limits, so that a refusal counts nothing.
        # Each question needs a token, a kept suggestion too: it is free, but it
        # makes a conversation, and its follow-up calls the model. When
        # Cloudflare does not answer, the question is refused: an answer then
        # would let any made-up token through for as long as Cloudflare is away.
        if not body.turnstile_token:
            raise HTTPException(403, BOT_CHECK_FAILED)
        verdict = service.verify_token(body.turnstile_token, address)
        if verdict == "unavailable":
            raise HTTPException(503, BOT_CHECK_UNAVAILABLE)
        if verdict != "passed":
            raise HTTPException(403, BOT_CHECK_FAILED)
        new = body.conversation_id is None
        # A kept suggestion calls no model, so the daily limits and the slots are
        # only for the other questions.
        paid = service.kept_turn(body.question, new) is None
        day: date | None = None
        if paid:
            try:
                day = service.daily.take(address)
            except DailyLimitReached as reached:
                if reached.scope == "address":
                    limit = service.settings.daily_limit_per_address
                    # No Retry-After: the page shows the text and no countdown of hours.
                    raise HTTPException(429, ADDRESS_LIMIT.format(limit=limit)) from None
                raise HTTPException(503, SITE_LIMIT) from None
            if not service.take_slot():
                service.daily.give_back(address, day)
                raise HTTPException(503, SERVICE_BUSY)
        started = False
        try:
            try:
                conversation_id = service.conversations.begin(body.conversation_id)
            except UnknownConversation:
                raise HTTPException(404, ENDED) from None
            except BusyConversation:
                raise HTTPException(409, BUSY) from None
            events: queue.Queue[str | None] = queue.Queue()
            # The agent is synchronous. On its own thread, each event leaves when it
            # is made, and the turn ends also when the client goes away.
            threading.Thread(
                target=service.run_turn,
                args=(body.question, conversation_id, new, events, paid),
                daemon=True,
            ).start()
            started = True
        finally:
            # Once the thread runs, run_turn frees the slot. Before that, any error
            # (a refusal or one that nobody expects) must free it here, or ten of
            # them refuse every paid question until a restart.
            if paid and day is not None and not started:
                service.free_slot()
                service.daily.give_back(address, day)
        return StreamingResponse(
            stream(events),
            media_type="text/event-stream",
            # A proxy that buffers a response holds each step until the answer
            # is complete. This header tells it to send each event at once.
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
