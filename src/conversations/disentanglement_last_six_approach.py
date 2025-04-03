import logging
from ollama import chat
from pydantic import BaseModel, Field

from datatypes import ClassifiedMessage, Conversation, Message

logger = logging.getLogger(__name__)


class Response(BaseModel):
    '''output describing whether the new message is continuation of any of the previous message'''
    new_message: Message = Field(description="the new incoming message")
    option: int = Field(description="Which of the option is this message a continuation, -1 if niether of them")
    reason: str = Field(description="reason for your choice")


def __format_options(previous_messages):
    option_str = ''
    for idx, msg in enumerate(previous_messages):
        option_str += f'Option {idx+1}: {msg.message}'
        option_str += '\n'
    return option_str


def classify_message(previous_messages: list[Message], msg: ClassifiedMessage, model: str) -> Response:
    examples = """

    """

    prompt = f"""
        As one of the best and most reasonable data taggers,
        
        You are provided with upto 6 options that represent the last 6 messages that have come in and a new message,
        you need to provide which of the last 6 options can be a parent to the new message, if neither of the options
        can be a parent, provide -1

        example:
        {examples}

        Here are your options:
        {__format_options(previous_messages)}

        the new message:
        {msg.message}

        Provide your classification response with reasoning below,
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


def llm_based_classifier(last_6_messages: list[ClassifiedMessage], message: ClassifiedMessage) -> int:
    classification = classify_message(last_6_messages, message, 'qwq:32b')
    return classification.option
