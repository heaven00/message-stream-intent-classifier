from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class CalendarClassification(BaseModel):
    label: Literal["LABEL_0", "LABEL_1"]
    score: float


class Message(BaseModel):
    seqid: int
    ts: datetime
    user: str
    message: str


class ClassifiedMessage(Message):
    classification: CalendarClassification


class DetectedCalendarEvent(BaseModel):
    lines: list[Message]


class Conversation(BaseModel):
    lines: list[Message] = []
    users: set[str] = set()
    last_updated: datetime | None = None
    completed: bool = False
