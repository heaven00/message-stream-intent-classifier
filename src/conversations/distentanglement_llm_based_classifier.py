from ollama import chat
from pydantic import BaseModel, Field

from datatypes import ClassifiedMessage, Conversation, Message


class Response(BaseModel):
    '''output describing whether the new message is part of the previous conversation or not'''
    previous_conversation: list[Message]
    new_message: Message
    matches: bool
    reason: str


def classify_message(previous_messages: list[ClassifiedMessage], msg: ClassifiedMessage, model: str) -> Response:
    prompt = f"""
        You are provided with a conversation with user and the message they wrote in a IRC or slack channel you need to tell if the given new message is part of the conversation or not
        
        Conversation: 
        {previous_messages}

        New Message:
        {msg}
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
    return classify_message(conversation.lines, message, 'qwq:32b').matches