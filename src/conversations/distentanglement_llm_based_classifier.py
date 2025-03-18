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
    examples = """
    Example where matches is True 
    
    #1
    Conversation:
    user: blah, message: Hi, I need help with my ollama setup
    user: blah, message: I am not able to figure out how to set up the context window

    New Message:
    user: bar, message: just set the num_ctx parameter to what you need it to be and also look at the model card to know what's usable with the model you are hosting

    Response:
    matches: True
    reason: It is a direct response to the question asked by the user blah

    #2
    Conversation:
    user: blah, message: Hi, I need help with my ollama setup

    New Message:
    user: blah, message: I am not able to figure out how to set up the context window

    Response:
    matches: True
    reason: It is a continuation of the message by the same user

    Example where matches is False

    #1
    Conversation:
    user: blah, message: Hi, I need help with my ollama setup
    user: blah, message: I am not able to figure out how to set up the context window

    New Message:
    user: foo, message: did you check out the latest qwen reasoning model?

    Response:
    matches: False
    reason: It has nothing to do with the ollama setup debugging

    #2
    Conversation:
    user: blah, message: Hi, I need help with my ollama setup

    New Message:
    user: bar, message: foo, how is your day going?

    Response:
    matches: False
    reason: the message from user bar is not related to message from user blah
    """

    prompt = f"""
        You are provided with a conversation with user and the message they wrote in an IRC or slack channel and a new message, you need to classify whether the 
        new message is part of the conversation or not, reply True if the new message is part of the conversation or reply False if the new message is not part of the
        conversation, provide reason for your choice.

        example:
        {examples}

        Here is the Conversation so far: 
        {[__format_msg(msg) for msg in previous_messages]}

        the new message:
        {__format_msg(msg)}

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
    return Response.model_validate_json(response.message.content)


def llm_based_classifier(conversation: Conversation, message: ClassifiedMessage) -> bool:
    classification = classify_message(conversation.lines, message, 'qwq:32b')
    return classification.matches