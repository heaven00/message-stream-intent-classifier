from pydantic import BaseModel
from typing import Literal


class Message(BaseModel):
    seqid: int
    ts: float
    user: str
    message: str


class CalendarClassification(BaseModel):
    label: Literal["LABEL_0", "LABEL_1"]
    score: float


class DetectedCalendarEvent(BaseModel):
    lines: list[Message]
