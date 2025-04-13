from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class CalendarClassification(BaseModel):
    # label 1 = is calendar event
    label: Literal["LABEL_0", "LABEL_1"]
    score: float


class Message(BaseModel):
    seqid: int
    ts: datetime
    user: str
    message: str


class ClassifiedMessage(Message):
    classification: CalendarClassification


class Conversation(BaseModel):
    lines: list[Message] = []
    users: set[str] = set()
    last_updated: datetime | None = None
    suspended: bool = False
    completed: bool = False
    event_datetime: datetime | None = None


class CreateConversationEvent(BaseModel):
    message: ClassifiedMessage


class AddToConversationEvent(BaseModel):
    message: ClassifiedMessage
    previous_message: ClassifiedMessage
