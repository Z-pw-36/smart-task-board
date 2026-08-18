from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


type TaskStatus = Literal[
    "draft",
    "pending_confirmation",
    "pending_acceptance",
    "returned",
    "in_progress",
    "pending_review",
    "completed",
]
type TaskNodeStatus = Literal["pending", "in_progress", "completed"]
type ParticipantConfirmStatus = Literal["pending", "accepted", "returned"]


def _decimal_to_string(value: Decimal) -> str:
    return format(value, "f")


type DecimalString = Annotated[
    Decimal,
    PlainSerializer(_decimal_to_string, return_type=str, when_used="json"),
]
type NonNegativeDecimalString = Annotated[DecimalString, Field(ge=0)]
