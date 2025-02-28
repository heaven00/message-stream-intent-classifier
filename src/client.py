import asyncio
import os
import random
import websockets
from calendar_event_classifier import is_calendar_event
from datatypes import Message, Conversation
from dotenv import load_dotenv
from conversations.ops import mark_old_conversations, upsert_conversations


async def listen(url):
    conversations: list[Conversation] = []
    async with websockets.connect(url) as websocket:
        while True:
            message = Message.model_validate_json(await websocket.recv(decode=True))
            classified_message = is_calendar_event(message)
            conversations = upsert_conversations(
                conversations,
                classified_message,
                lambda x, y: random.choice([True, False]),
            )
            conversations = mark_old_conversations(conversations)



def main():
    load_dotenv()
    asyncio.run(listen(os.getenv("WS_SOCK")))
