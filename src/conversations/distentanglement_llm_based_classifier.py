import logging
from ollama import chat
from pydantic import BaseModel, Field

from datatypes import ClassifiedMessage, Conversation, Message

logger = logging.getLogger(__name__)


class Response(BaseModel):
    '''output describing whether the new message is part of the previous conversation or not'''
    previous_conversation: list[Message] = Field(description="list of messages from the conversation")
    new_message: Message = Field(description="the new incoming message")
    matches: bool = Field(description="True if the conversation matches and False if it does not matches")
    reason: str = Field(description="reason for the value in matches")


def __format_msg(msg: ClassifiedMessage):
    return {
        "user": msg.user,
        "timestamp": msg.ts.strftime("%Y-%m-%d-%H:%M:%S"),
        "message": msg.message
    }


def classify_message(previous_messages: list[ClassifiedMessage], msg: ClassifiedMessage, model: str) -> Response:
    prompt = f"""
        You are provided with a conversation with user and the message they wrote in an IRC or slack channel and a new message, you need to classify whether the 
        new message is part of the conversation or not, reply True if the new message is part of the conversation or reply False if the new message is not part of the
        conversation, provide reason for your choice.
        
        Conversation: 
        {[__format_msg(msg) for msg in previous_messages]}

        New Message:
        {__format_msg(msg)}

        Provide your classification response with reasoning below,
    """
    response = chat(
        messages = [
            {'role': 'user', 'content': prompt},
        ],
        model=model,
        format=Response.model_json_schema(),
        options={
            'temperature': 0
        }
    )
    return Response.model_validate_json(response.message.content)


def llm_based_classifier(conversation: Conversation, message: ClassifiedMessage) -> bool:
    classification = classify_message(conversation.lines, message, 'deepseek-r1:8b')
    logging.info(classification)
    return classification.matches