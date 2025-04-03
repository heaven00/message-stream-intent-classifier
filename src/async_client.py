import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4
from pydantic import BaseModel, ValidationError
import websockets
from functools import partial
from websockets.exceptions import ConnectionClosedOK
from calendar_event_classifier import is_calendar_event
from conversations.disentanglement_last_six_approach import llm_based_classifier
from conversations.ops import (
    add_message_to_conversation,
    disentangle_message,
    update_completed_conversation,
)
from conversations.disentanglement_rule_based_classifier import rule_based_classifier
from datatypes import (
    AddToConversationEvent,
    ClassifiedMessage,
    CreateConversationEvent,
    Message,
    Conversation,
)
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
    valid_message_queue: asyncio.Queue,
    classified_message_queue: asyncio.Queue,
    processed_messages_metric,
):
    while True:
        message = await valid_message_queue.get()
        classified_message = is_calendar_event(message)
        asyncio.create_task(classified_message_queue.put(classified_message))
        processed_messages_metric.update(1)  # Increment after processing


async def _is_continuation(
    prev_messages: list[ClassifiedMessage], message: ClassifiedMessage
) -> int:
    return llm_based_classifier(prev_messages, message)


async def disentangle_message(
    classified_message_queue: asyncio.Queue, state_update_queue: asyncio.Queue
):
    last_6_messages = []
    while True:
        classified_message = await classified_message_queue.get()
        if len(last_6_messages) == 0:
            await state_update_queue.put(
                CreateConversationEvent(message=classified_message)
            )
        else:
            index = await _is_continuation(last_6_messages, classified_message)
            if index != -1 and index <= len(last_6_messages):
                await state_update_queue.put(
                    AddToConversationEvent(
                        message=classified_message,
                        previous_message=last_6_messages[index],
                    )
                )
            else:
                await state_update_queue.put(
                    CreateConversationEvent(message=classified_message)
                )
        last_6_messages.append(classified_message)
        if len(last_6_messages) > 6:
            last_6_messages.pop(0)


async def conversation_manager(
    state_update_queue: asyncio.Queue, conversations: dict, conv_seq_id_map: dict
):
    while True:
        # maintain a list of conversations and trigger
        event = await state_update_queue.get()
        if isinstance(event, AddToConversationEvent):
            exisitng_conversation_uuid = conv_seq_id_map[
                event.previous_message.seqid
            ]
            conv = conversations[exisitng_conversation_uuid]
            conversations[exisitng_conversation_uuid] = add_message_to_conversation(
                conv, event.message
            )
            conv_seq_id_map[event.message.seqid] = exisitng_conversation_uuid
        elif isinstance(event, CreateConversationEvent):
            conv_uuid = str(uuid4())
            conversations[conv_uuid] = add_message_to_conversation(
                Conversation(), event.message
            )
            conv_seq_id_map[event.message.seqid] = conv_uuid
        else:
            raise Exception("Unknown message type")


async def archive_completed_conversations(
    conversations: list[Conversation], conversation_archival_queue: asyncio.Queue
):
    updated_convs = update_completed_conversation(
        conversations,
        seconds_lapsed=30,
        current_time=datetime.now(timezone.utc),
    )

    for conv in updated_convs:
        if conv.completed:
            await conversation_archival_queue.put(conv)


async def start_ingestion(
    message_data, valid_message_queue: asyncio.Queue, messages_received
):
    try:
        message = Message.model_validate_json(message_data)
        await valid_message_queue.put(message)
        messages_received.update(1)  # Increment on each received message
    except ValidationError as e:
        # fail silently for now
        # this message should be sent to another queue for debugging
        logger.error(e)
        pass


async def listen(url, ingestion_callback):
    async with websockets.connect(url) as websocket:
        while True:
            message_data = await websocket.recv()
            # should there be no await here?
            asyncio.create_task(ingestion_callback(message_data))


async def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # state
    conversations = {}
    conv_seq_id_map = {}

    # metrics
    metrics = {
        "messages_received": tqdm.tqdm(
            desc="Messages Received", unit=" msgs", colour="green"
        ),
        "active_conversations": tqdm.tqdm(
            desc="Active Conversations",
            unit=" convs",
            colour="blue",
            total=float("inf"),  # Unlimited total for dynamic count
        ),
        "processed_messages": tqdm.tqdm(
            desc="Messages Processed", unit=" msgs", colour="yellow"
        ),
    }

    # declare queues
    valid_message_queue = asyncio.Queue()
    classified_message_queue = asyncio.Queue()
    conversation_archival_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()  # Added

    ingest = partial(
        start_ingestion,
        valid_message_queue=valid_message_queue,
        messages_received=metrics["messages_received"],
    )

    tasks = [
        listen(os.getenv("WS_SOCK"), ingest),
        classify_message(
            valid_message_queue, classified_message_queue, metrics["processed_messages"]
        ),
        # redo from here, this needs to be cleaned up
        disentangle_message(classified_message_queue, state_update_queue),
        conversation_manager(state_update_queue, conversations, conv_seq_id_map),
        archive_completed_conversations(conversations, conversation_archival_queue),
        store_probable_calendar_conversations(conversation_archival_queue),
    ]
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except (KeyboardInterrupt, ConnectionClosedOK):
        logging.info("Initiating graceful shutdown...")
        current_tasks = asyncio.all_tasks()
        for task in current_tasks:
            if task != asyncio.current_task():
                task.cancel()

        # Wait for tasks to complete/cancel
        await asyncio.gather(*current_tasks, return_exceptions=True)
        logging.info("All tasks completed/cancelled")
        # Clean up queues
        for queue in [
            valid_message_queue,
            classified_message_queue,
            conversation_archival_queue,
            state_update_queue,  # Added
        ]:
            queue.put_nowait(None)  # Signal completion
        logging.info("All Queues cleared")

        # Clean up tqdm metrics
        for progress_bar in metrics.values():
            progress_bar.close()
        logging.info("Graceful shutdown completed.")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
