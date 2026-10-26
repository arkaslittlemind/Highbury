"""The analyst agent: a model that answers a question with the data tools.

The tools run in this process. They are the same functions that the MCP server
serves.
"""

import functools
import inspect
import itertools
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.structured_output import StructuredOutputError
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from analyst import tools
from analyst.answer import Answer, ToolRecord
from analyst.prompt import build_system_prompt
from analyst.settings import model_name
from analyst.verifier import Verification, verify

TOOL_CALL_LIMIT = 10
# A model can call no tool and still not end: it can give an answer of a wrong
# shape again and again. Each tool call needs one model call at most, and the
# rest is for the answer and its corrections.
MODEL_CALL_LIMIT = TOOL_CALL_LIMIT + 5

NO_ANSWER = "The model gave no structured answer."

# What the model reads of a chart. The data of the chart stays in the record.
CHART_KEYS = ("id", "type", "title")


class Usage(BaseModel):
    """What one question used of the model."""

    model_calls: int = 0
    # The sums of what the provider reported. A reply with no report adds nothing.
    input_tokens: int = 0
    output_tokens: int = 0


class AgentError(Exception):
    """The turn gave no answer. The text is safe to show: it holds no secret, no
    connection string, and no question text."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        # What the turn used before it failed. None when no turn started.
        self.usage = usage


class Turn(BaseModel):
    # Its claims are only the ones that passed the check.
    answer: Answer
    # The tool calls of this question only, in the order of the calls.
    records: list[ToolRecord]
    verification: Verification
    usage: Usage


@dataclass
class RunContext:
    """The state of one question. One agent answers many questions at the same time."""

    # The key is the place of the call in the conversation. The calls of one model
    # reply run at the same time, so the order in which they end is not their order.
    records: dict[tuple[int, int], ToolRecord] = field(default_factory=dict)
    # The number of the next tool call: 1 for the first call of the question.
    call_numbers: Iterator[int] = field(default_factory=lambda: itertools.count(1))
    usage: Usage = field(default_factory=Usage)
    # The hooks of ask. They can run on more than one thread at the same time.
    on_step: Callable[[int, str], None] | None = None
    on_record: Callable[[ToolRecord], None] | None = None


def model_text(result: BaseModel) -> str:
    """Return the JSON that the model reads for a tool result."""
    data = result.model_dump(mode="json")
    if isinstance(result, tools.ChartResult) and result.chart is not None:
        # A shot map holds each shot of a season. The model does not need them again.
        data["chart"] = {key: data["chart"][key] for key in CHART_KEYS}
    return json.dumps(data, ensure_ascii=False)


def agent_tool(function: Callable[..., BaseModel]) -> StructuredTool:
    """Return the tool with the name, the docstring, and the arguments of the function."""

    @functools.wraps(function)
    def call(*args: Any, **kwargs: Any) -> tuple[str, BaseModel]:
        result = function(*args, **kwargs)
        return model_text(result), result

    return StructuredTool.from_function(
        call,
        # The docstring as it is has the indent of the code.
        description=inspect.getdoc(function),
        response_format="content_and_artifact",
    )


AGENT_TOOLS = [
    agent_tool(function)
    for function in (
        tools.get_data_catalog,
        tools.get_schema,
        tools.resolve_player,
        tools.run_sql,
        tools.build_chart,
    )
]


def call_place(request: ToolCallRequest) -> tuple[int, int]:
    """Return the place of the call: the model reply that made it, then its place there."""
    messages = request.state["messages"]
    # The reply is not always the last message: the answer of a model can come
    # in the same reply as a tool call, and its message then follows the reply.
    reply = max(index for index, message in enumerate(messages) if isinstance(message, AIMessage))
    ids = [call["id"] for call in messages[reply].tool_calls]
    return reply, ids.index(request.tool_call["id"])


@wrap_tool_call
def limit_tool_calls(request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]) -> Any:
    """Stop the turn at the call after the limit, before the tool runs.

    The limit middleware of LangChain also counts the tool call that carries the
    structured answer of some models, so the limit would differ by model.
    """
    context = request.runtime.context
    number = next(context.call_numbers)
    if number > TOOL_CALL_LIMIT:
        raise AgentError(
            f"The question needed more than {TOOL_CALL_LIMIT} tool calls.", context.usage
        )
    if context.on_step:
        context.on_step(number, request.tool_call["name"])
    return handler(request)


@wrap_tool_call
def record_tool_call(request: ToolCallRequest, handler: Callable[[ToolCallRequest], Any]) -> Any:
    """Keep each tool call of the question with its full result."""
    message = handler(request)
    if isinstance(message, ToolMessage):
        if isinstance(message.artifact, BaseModel):
            result = message.artifact.model_dump(mode="json")
        else:
            result = {"error": str(message.content)}
        context = request.runtime.context
        record = ToolRecord(
            name=request.tool_call["name"], args=request.tool_call["args"], result=result
        )
        context.records[call_place(request)] = record
        if context.on_record:
            context.on_record(record)
    return message


@wrap_model_call
def name_model_failure(request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
    """Turn a failure of the provider into an error with a text that is safe to show."""
    usage = request.runtime.context.usage
    try:
        return handler(request)
    except StructuredOutputError as error:
        raise AgentError(NO_ANSWER, usage) from error
    except Exception as error:
        # The providers have no shared error class, and the text of their errors
        # can repeat the request. Only the class name goes into the text.
        raise AgentError(f"The model call failed ({type(error).__name__}).", usage) from error


@wrap_model_call
def count_usage(
    request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
) -> ModelResponse:
    """Add each model call and its tokens to the usage of the question."""
    usage = request.runtime.context.usage
    # A call that fails is a call too: the provider can bill it.
    usage.model_calls += 1
    response = handler(request)
    for message in response.result:
        if isinstance(message, AIMessage) and message.usage_metadata:
            usage.input_tokens += message.usage_metadata["input_tokens"]
            usage.output_tokens += message.usage_metadata["output_tokens"]
    return response


def load_model() -> BaseChatModel:
    name = model_name()
    try:
        return init_chat_model(name)
    except Exception as error:
        # An unknown provider, a package that is not installed, or no API key.
        raise AgentError(
            f"The model of ANALYST_MODEL ({name}) did not load ({type(error).__name__})."
        ) from error


def build_agent(model: BaseChatModel | None = None) -> CompiledStateGraph:
    """Return the agent. Its prompt holds the catalog and the views as they are now.

    With no model, the model is the one that ANALYST_MODEL names.
    """
    model = model or load_model()
    catalog, schema = tools.get_data_catalog(), tools.get_schema()
    for result in (catalog, schema):
        if result.error:
            raise AgentError(result.error)
    return create_agent(
        model,
        AGENT_TOOLS,
        system_prompt=build_system_prompt(catalog, schema),
        middleware=[
            ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="error"),
            name_model_failure,
            count_usage,
            limit_tool_calls,
            record_tool_call,
        ],
        response_format=Answer,
        context_schema=RunContext,
        # Memory for the life of the process: enough for a follow-up question. The
        # checkpoint keeps the answer too, and it reads back only the types named here.
        checkpointer=InMemorySaver(
            serde=JsonPlusSerializer(allowed_msgpack_modules=[("analyst.answer", "Answer")])
        ),
    )


def ask(
    agent: CompiledStateGraph,
    question: str,
    thread_id: str,
    *,
    on_step: Callable[[int, str], None] | None = None,
    on_record: Callable[[ToolRecord], None] | None = None,
) -> Turn:
    """Answer one question. One thread id is one conversation.

    on_step gets the number and the tool name of each tool call before the tool
    runs. on_record gets the record of each call when the call ends. The calls
    of one model reply run at the same time, so a hook must be safe for threads.

    After AgentError the thread can hold a tool call with no result, so do not
    ask on that thread again.
    """
    context = RunContext(on_step=on_step, on_record=on_record)
    try:
        state = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"configurable": {"thread_id": thread_id}},
            context=context,
        )
    except ModelCallLimitExceededError as error:
        raise AgentError(
            f"The question needed more than {MODEL_CALL_LIMIT} model calls.", context.usage
        ) from error
    answer = state.get("structured_response")
    if answer is None:
        raise AgentError(NO_ANSWER, context.usage)
    records = [record for _, record in sorted(context.records.items())]
    answer, verification = verify(answer, records)
    return Turn(answer=answer, records=records, verification=verification, usage=context.usage)
