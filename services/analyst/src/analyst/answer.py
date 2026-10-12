"""The answer of the agent: what it says, and which tool output backs each number."""

from typing import Literal

from pydantic import BaseModel, JsonValue


class ToolRecord(BaseModel):
    name: str
    args: dict[str, JsonValue]
    # The JSON form of the result of the tool. Only an error text when the call
    # did not reach the tool.
    result: dict[str, JsonValue]


class Claim(BaseModel):
    text: str
    value: float
    unit: str
    # The call_id of the run_sql result whose rows hold the value. It is not the
    # id that the model provider gives to a tool call.
    tool_call_id: str


class ChartRef(BaseModel):
    # ChartSpec.id of a build_chart result.
    id: str


class Answer(BaseModel):
    status: Literal["answered", "unavailable", "out_of_scope"]
    summary: str
    claims: list[Claim]
    charts: list[ChartRef]
    caveats: list[str]
    # Used when the status is unavailable: a related thing that the data can show.
    alternative: str | None
