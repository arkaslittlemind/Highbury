"""The claim check: each number of an answer against the recorded tool output.

It is plain code, not a model call, so the same answer always gets the same check.
"""

import re
from collections.abc import Iterator, Sequence
from typing import Literal

from pydantic import BaseModel, JsonValue

from analyst.answer import Answer, Claim, ToolRecord

TOLERANCE = 0.01
# abs(0.76 - 0.75) is a little more than 0.01 in binary floats, and that
# difference must pass.
FLOAT_SLACK = 1e-9

SEASON_LABELS = ("2003-04", "2025-26")
# People and models also write a label with an en dash or with a slash.
LABELS = "|".join(label.replace("-", "[-\N{EN DASH}/]") for label in SEASON_LABELS)
# Numbers in the summary that are not statistics.
NOT_A_STATISTIC = re.compile(rf"(?<!\d)(?:{LABELS}|\bper\s+90)(?!\.?\d)", re.IGNORECASE)
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?")


class RemovedClaim(BaseModel):
    claim: Claim
    reason: Literal["call_not_found", "value_not_found"]


class Verification(BaseModel):
    # The number of claims that the model gave.
    checked: int
    passed: int
    removed: list[RemovedClaim]
    # Numbers of the summary, as written, that no passed claim backs.
    unbacked_numbers: list[str]


def cells(result: dict[str, JsonValue]) -> Iterator[JsonValue]:
    rows = result.get("rows")
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, list):
            yield from row


def cell_matches(cell: JsonValue, value: float) -> bool:
    """An integer cell is a count and must be equal. A float cell is an xG or a rate."""
    # A boolean is an int in Python, and it is not a count.
    if isinstance(cell, bool):
        return False
    if isinstance(cell, int):
        return cell == value
    if isinstance(cell, float):
        return abs(cell - value) <= TOLERANCE + FLOAT_SLACK
    return False


def unbacked_numbers(summary: str, values: list[float]) -> list[str]:
    """Return the numbers of the summary that none of the values backs."""
    magnitudes = [abs(value) for value in values]
    unbacked = []
    for text in NUMBER.findall(NOT_A_STATISTIC.sub(" ", summary)):
        number = float(text.replace(",", ""))
        # A number with no decimal part is written as a count.
        slack = TOLERANCE + FLOAT_SLACK if "." in text else 0
        backed = any(abs(magnitude - number) <= slack for magnitude in magnitudes)
        if not backed and text not in unbacked:
            unbacked.append(text)
    return unbacked


def verify(answer: Answer, records: Sequence[ToolRecord]) -> tuple[Answer, Verification]:
    """Return the answer with only the claims that the records support, and the check.

    records holds the tool calls of the question of the answer.
    """
    passed: list[Claim] = []
    removed: list[RemovedClaim] = []
    for claim in answer.claims:
        # Only a run_sql result holds rows. A chart result has a call_id too.
        cited = [
            record.result
            for record in records
            if record.name == "run_sql" and record.result.get("call_id") == claim.tool_call_id
        ]
        if not cited:
            removed.append(RemovedClaim(claim=claim, reason="call_not_found"))
        elif any(cell_matches(cell, claim.value) for result in cited for cell in cells(result)):
            passed.append(claim)
        else:
            removed.append(RemovedClaim(claim=claim, reason="value_not_found"))
    verification = Verification(
        checked=len(answer.claims),
        passed=len(passed),
        removed=removed,
        unbacked_numbers=unbacked_numbers(answer.summary, [claim.value for claim in passed]),
    )
    return answer.model_copy(update={"claims": passed}), verification
