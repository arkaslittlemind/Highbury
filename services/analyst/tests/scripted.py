"""A model for the tests: it gives the replies of the test and calls no provider."""

import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

ANSWER = {
    "status": "answered",
    "summary": "Thierry Henry took 2 shots in 2003-04.",
    # A claim needs the id of a query of the turn, so a test that needs one gives it.
    "claims": [],
    "charts": [],
    "caveats": [],
    "alternative": None,
}
SHOTS_SQL = "SELECT * FROM v_shots WHERE player = 'Thierry Henry'"
COUNT_SQL = "SELECT count(*) AS shots FROM v_shots"


def shots_claim(tool_call_id: str) -> dict:
    """The claim that the rows of COUNT_SQL support."""
    return {
        "text": "Henry took 2 shots",
        "value": 2,
        "unit": "shots",
        "tool_call_id": tool_call_id,
    }


class ScriptedModel(BaseChatModel):
    """A model that gives the replies of the test, in order, and keeps what it was sent.

    A reply is a message, an error to raise, or a function from the tool results
    that the model has read to a message.
    """

    replies: list[Any]
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            # The reply needs an id that a tool made in this turn.
            reply = reply(tool_texts(messages))
        return ChatResult(generations=[ChatGeneration(message=reply)])


def calls(*tool_calls: tuple[str, dict]) -> AIMessage:
    """One reply of the model that calls the tools."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{name}_{number}"}
            for number, (name, args) in enumerate(tool_calls)
        ],
    )


def answer(**changes) -> AIMessage:
    return calls(("Answer", {**ANSWER, **changes}))


def tool_texts(messages: list[BaseMessage]) -> dict[str, dict]:
    """What the model read from each tool, by tool name. The last call of a tool wins."""
    return {
        message.name: json.loads(message.content)
        for message in messages
        # The structured answer of a turn before is a tool message too, with no JSON.
        if isinstance(message, ToolMessage) and message.name != "Answer"
    }


def with_usage(reply: AIMessage, input_tokens: int, output_tokens: int) -> AIMessage:
    """The reply with the token counts that a provider reports."""
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return reply.model_copy(update={"usage_metadata": usage})
