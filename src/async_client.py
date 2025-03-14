import asyncio
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
import logging

logger = logging.getLogger(__name__)


class AppState(BaseModel):
    conversations: list[Conversation] = []


async def store_probable_calendar_conversations(
    conversational_archival_queue: asyncio.Queue,
):
    conv = await conversational_archival_queue.get()
    async with aiof.open(f"results/event_{conv.lines[0].seqid}_v1.json", "w") as out:
        await out.write(conv.model_dump_json())
        await out.flush()


async def classify_message(
    valid_message_queue: asyncio.Queue, classified_message_queue: asyncio.Queue
):
    while True:
        message = await valid_message_queue.get()
        classified_message = is_calendar_event(message)
        await classified_message_queue.put(classified_message)


async def match_conversation(classified_message_queue: asyncio.Queue, state: AppState):
    # update the conversation state
    classified_message = await classified_message_queue.get()

    confident_it_is_a_calendar_event = (
        classified_message.classification.label == "LABEL_1"
        and classified_message.classification.score > 0.8
    )

    if confident_it_is_a_calendar_event:
        state.conversations = disentangle_message(
            state.conversations, classified_message, rule_based_classifier
        )

        logger.info(
            f"Received new message: '{classified_message.message}'"
            f" with confidence {classified_message.classification.score}"
        )


async def completed_conversations(
    conversation_archival_queue: asyncio.Queue, state: AppState
):
    for conv in state.conversations:
        if conv.completed:
            await conversation_archival_queue.put(conv)


async def flush_all_conversations(
    conversation_archival_queue: asyncio.Queue, state: AppState
):
    for conv in state.conversations:
        await conversation_archival_queue.put(conv)


async def listen(url, valid_message_queue: asyncio.Queue):
    try:
        websocket = await websockets.connect(url)
        async with websocket:
            message = Message.model_validate_json(await websocket.recv(decode=True))
            await valid_message_queue.put(message)

    except ConnectionClosedOK:
        logger.info("Completed processing messages in WebSocket")
        logger.debug("Writing out any pending conversations")

    except ConnectionClosedError as e:
        logger.error(f"Connection closed unexpectedly: {e}", exc_info=True)

    except InvalidURI:
        logger.error(f"Invalid WebSocket URI: {url}")


def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # state
    state = AppState()

    # declare queues
    valid_message_queue = asyncio.Queue()
    classified_message_queue = asyncio.Queue()
    conversation_archival_queue = asyncio.Queue()

    asyncio.gather(
        listen(os.getenv("WS_SOCK"), valid_message_queue),
        classify_message(valid_message_queue, classified_message_queue),
        match_conversation(classified_message_queue, state),
        completed_conversations(conversation_archival_queue, state),
        store_probable_calendar_conversations(conversation_archival_queue),
    )

    asyncio.gather(
        flush_all_conversations(conversation_archival_queue, state),
        store_probable_calendar_conversations(conversation_archival_queue),
    )


if __name__ == "__main__":
    main()
