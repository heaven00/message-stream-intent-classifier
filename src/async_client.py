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
import tqdm


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
    valid_message_queue: asyncio.Queue, classified_message_queue: asyncio.Queue,
    processed_messages_metric
):
    while True:
        message = await valid_message_queue.get()
        classified_message = is_calendar_event(message)
        await classified_message_queue.put(classified_message)
        processed_messages_metric.update(1)  # Increment after processing


async def match_conversation(
    classified_message_queue: asyncio.Queue, state: AppState,
    active_conversations_metric
):
    while True:
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
        
        current_active = len(state.conversations)
        active_conversations_metric.n = current_active  # Set exact count
        active_conversations_metric.refresh()  


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


async def listen(url, valid_message_queue: asyncio.Queue, messages_received):
    try:
        async with websockets.connect(url) as websocket:
            while True:
                message_data = await websocket.recv()
                message = Message.model_validate_json(message_data)
                await valid_message_queue.put(message)
                messages_received.update(1)  # Increment on each received message
    except ConnectionClosedOK:
        logger.info("Completed processing messages in WebSocket")
        logger.debug("Writing out any pending conversations")

    except ConnectionClosedError as e:
        logger.error(f"Connection closed unexpectedly: {e}", exc_info=True)

    except InvalidURI:
        logger.error(f"Invalid WebSocket URI: {url}")


async def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # state
    state = AppState()

    # metrics
    metrics = {
        'messages_received': tqdm.tqdm(
            desc="Messages Received",
            unit=" msgs",
            colour="green"
        ),
        'active_conversations': tqdm.tqdm(
            desc="Active Conversations",
            unit=" convs",
            colour="blue",
            total=float('inf')  # Unlimited total for dynamic count
        ),
        'processed_messages': tqdm.tqdm(
            desc="Messages Processed",
            unit=" msgs",
            colour="yellow"
        )
    }

    # declare queues
    valid_message_queue = asyncio.Queue()
    classified_message_queue = asyncio.Queue()
    conversation_archival_queue = asyncio.Queue()

    await asyncio.gather(
        listen(os.getenv("WS_SOCK"), valid_message_queue, metrics['messages_received']),
        classify_message(valid_message_queue, classified_message_queue, metrics['processed_messages']),
        match_conversation(classified_message_queue, state, metrics['active_conversations']),
        completed_conversations(conversation_archival_queue, state),
        store_probable_calendar_conversations(conversation_archival_queue),
        flush_all_conversations(conversation_archival_queue, state),
    )


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
