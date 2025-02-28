import asyncio
from datetime import datetime, timezone
import os
from pydantic import BaseModel
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError, InvalidURI
from calendar_event_classifier import is_calendar_event
from conversations.ops import disentangle_message, update_completed_conversation
from conversations.disentanglement_classifier import rule_based_classifier
from datatypes import Message, Conversation
from dotenv import load_dotenv
import aiofiles as aiof


class AppState(BaseModel):
    calender_conversations: list[Conversation] = []


async def listen(url):
    state = AppState()
    try:
        async with websockets.connect(url) as websocket:
            while True:
                message = Message.model_validate_json(await websocket.recv(decode=True))
                classified_message = is_calendar_event(message)
                
                confident_it_is_a_calendar_event = (
                    classified_message.classification.label == 'LABEL_1' 
                    and 
                    classified_message.classification.score > 0.8
                )
                if confident_it_is_a_calendar_event:
                    state.calender_conversations = disentangle_message(
                        state.calender_conversations,
                        classified_message,
                        rule_based_classifier
                    )
                    print(f"got new message: {classified_message.message}, confidence: {classified_message.classification.score}")
                state.calender_conversations = update_completed_conversation(
                    conversations=state.calender_conversations, 
                    seconds_lapsed=30,
                    current_time=datetime.now(timezone.utc)
                )
                for conv in state.calender_conversations:
                    if conv.completed:
                        await store_probable_calendar_conversations(conv)
                        state.calender_conversations.remove(conv)
    except ConnectionClosedOK:
        print("Completed Processing the messages in the websocket")
    except ConnectionClosedError as e:
        print(f"Connection closed from source, {e}")
    except InvalidURI:
        print(f"{url} invalid websocket URI")


async def store_probable_calendar_conversations(conv: Conversation):
    async with aiof.open(f"results/event_{conv.lines[0].seqid}_v1.json", "w") as out:
        await out.write(conv.model_dump_json())
        await out.flush()


def main():
    load_dotenv()
    asyncio.run(listen(os.getenv("WS_SOCK")))


if __name__ == "__main__":
    main()