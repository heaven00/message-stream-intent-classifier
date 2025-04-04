from datetime import datetime
import logging
from ollama import chat
from pydantic import BaseModel, Field

from datatypes import ClassifiedMessage, Conversation, Message

logger = logging.getLogger(__name__)


class Response(BaseModel):
    '''output describing whether the new message is part of the previous conversation or not'''
    conversation: list[Message] = Field(description="list of messages from the conversation")
    event_datetime: datetime = Field(description="Date time to be extracted from conversation")
    datetime_exists: bool = Field(description="set to False if the datetime does not exist and to True if datetime exist")
    reason: str = Field(description="reason for why the event is that datetime")


def __format_msg(msg: ClassifiedMessage):
    return {
        "user": msg.user,
        "timestamp": msg.ts.strftime("%Y-%m-%d-%H:%M:%S"),
        "message": msg.message
    }


def extract_event(conversation: list[Message], model: str) -> Response:
    examples = """
    """

    prompt = f"""
        Assume you are data annotator, and you are tasked with extracting date time for events in conversations, below you will be provided with conversation

        Here is the Conversation so far:
        {[__format_msg(msg) for msg in conversation]}


        Provide the event datetime below,
        Response:
    """
    response = chat(
        messages = [
            {'role': 'user', 'content': prompt},
        ],
        model=model,
        format=Response.model_json_schema(),
        options={
            'temperature': 0,
            'num_ctx': 8192
        }
    )
    return Response.model_validate_json(response.message.content or "")


def model(conversation: Conversation) -> datetime | None:
    result = extract_event(conversation.lines, 'qwq:32b')
    if result.datetime_exists:
        return result.event_datetime
    else:
        return None
