import asyncio
import os
import random
import websockets
from calendar_event_classifier import is_calendar_event
from datatypes import Message, Conversation
from dotenv import load_dotenv
from conversations.ops import update_completed_conversation, disentangle_message
from conversations.disentanglement_classifier import rule_based_classifier


async def listen(url):
    conversations: list[Conversation] = []
    async with websockets.connect(url) as websocket:
        while True:
            message = Message.model_validate_json(await websocket.recv(decode=True))
            classified_message = is_calendar_event(message)
            conversations = disentangle_message(
                conversations,
                classified_message,
                rule_based_classifier,
            )
            conversations = update_completed_conversation(conversations, 45)


def main():
    load_dotenv()
    asyncio.run(listen(os.getenv("WS_SOCK")))
