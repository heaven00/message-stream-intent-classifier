import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4
from pydantic import ValidationError
import websockets
from functools import partial
from websockets.exceptions import ConnectionClosedOK
from calendar_event_classifier import is_calendar_event
from conversations.disentanglement.last_six_approach import llm_based_classifier
from conversations.ops import (
    add_message_to_conversation,
    update_completed_conversation,
)
from datatypes import (
    AddToConversationEvent,
    ClassifiedMessage,
    CreateConversationEvent,
    Message,
    Conversation,
)
from dotenv import load_dotenv
import aiofiles
import logging


logger = logging.getLogger(__name__)

async def store_probable_calendar_conversations(
    conversational_archival_queue: asyncio.Queue,
):
    while True:
        conv = await conversational_archival_queue.get()
        if conv is None:
            break
        async with await aiofiles.open(
            f"results/event_{conv.lines[0].seqid}_v2.json", "w"
        ) as out:
            await out.write(conv.model_dump_json())
            await out.flush()


async def classify_message(
    valid_message_queue: asyncio.Queue,
    classified_message_queue: asyncio.Queue,
):
    while True:
        message = await valid_message_queue.get()
        if message is None:
            break
        classified_message = is_calendar_event(message)
        asyncio.create_task(classified_message_queue.put(classified_message))


async def _is_continuation(
    prev_messages: list[ClassifiedMessage], message: ClassifiedMessage
) -> int:
    return await llm_based_classifier(prev_messages, message)


async def classified_message_to_conversation(
    classified_message_queue: asyncio.Queue, state_update_queue: asyncio.Queue
):
    last_6_messages = []
    while True:
        classified_message = await classified_message_queue.get()
        if classified_message is None:
            break
        if len(last_6_messages) == 0:
            asyncio.create_task(state_update_queue.put(
                CreateConversationEvent(message=classified_message)
            ))
        else:
            index = await _is_continuation(last_6_messages, classified_message)
            if index != -1 and index <= len(last_6_messages):
                asyncio.create_task(state_update_queue.put(
                    AddToConversationEvent(
                        message=classified_message,
                        previous_message=last_6_messages[index - 1],
                    )
                ))
            else:
                asyncio.create_task(state_update_queue.put(
                    CreateConversationEvent(message=classified_message)
                ))
        last_6_messages.append(classified_message)
        if len(last_6_messages) > 6:
            last_6_messages.pop(0)


async def conversation_manager(
    state_update_queue: asyncio.Queue,
    conversations: dict,
    conv_seq_id_map: dict,
    conversation_archival_queue: asyncio.Queue,
):
    counter = 0
    while True:
        # maintain a list of conversations and trigger
        event = await state_update_queue.get()
        if event is None:
            print("Recieved Kill Signal", flush=True)
            break
        if isinstance(event, AddToConversationEvent):
            exisitng_conversation_uuid = conv_seq_id_map[event.previous_message.seqid]
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
        # every n messages trigger archive task
        if counter == 10:
            asyncio.create_task(
                archive_completed_conversations(
                    conversations, conversation_archival_queue
                )
            )


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


async def start_ingestion(message_data, valid_message_queue: asyncio.Queue):
    try:
        message = Message.model_validate_json(message_data)
        await valid_message_queue.put(message)
    except ValidationError as e:
        # fail silently for now
        # this message should be sent to another queue for debugging
        logger.error(e)
        pass


async def monitor_queue_sizes(queues: list[str, asyncio.Queue]):
    async def print_queues(queues):
        for name, queue in queues:
            print(name, queue.qsize(), flush=True)
    while True:
        await print_queues(queues)
        await asyncio.sleep(1)


async def listen(url, ingestion_callback):
    try:
        async with websockets.connect(url) as websocket:
            while True:
                message_data = await websocket.recv()
                # should there be no await here?
                asyncio.create_task(ingestion_callback(message_data))
    except ConnectionClosedOK:
        pass


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

    # declare queues
    valid_message_queue = asyncio.Queue()
    classified_message_queue = asyncio.Queue()
    conversation_archival_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()  # Added

    ingest = partial(
        start_ingestion,
        valid_message_queue=valid_message_queue,
    )

    queues_named_list = [
        ("valid_message_queue",valid_message_queue),
        ("classified_message_queue", classified_message_queue),
        ("conversation_archival_queued", conversation_archival_queue),
        ("state_update_queue", state_update_queue)
    ]

    try:
        async with asyncio.taskgroups.TaskGroup() as group:
            group.create_task(listen(os.getenv("WS_SOCK"), ingest))
            group.create_task(classify_message(valid_message_queue, classified_message_queue))
            group.create_task(classified_message_to_conversation(classified_message_queue, state_update_queue))
            group.create_task(conversation_manager(
                state_update_queue,
                conversations,
                conv_seq_id_map,
                conversation_archival_queue
            ))
            group.create_task(store_probable_calendar_conversations(conversation_archival_queue))
            group.create_task(monitor_queue_sizes(queues_named_list))

    except* (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Initiating graceful shutdown...")
        current_tasks = asyncio.all_tasks()
        for task in current_tasks:
            if task != asyncio.current_task():
                task.cancel()

        # Clean up queues
        for queue in [
            valid_message_queue,
            classified_message_queue,
            conversation_archival_queue,
            state_update_queue
        ]:
            queue.put_nowait(None)  # Signal completion
        logging.info("Sent close signal to all Queues")
        
        # Wait for tasks to complete/cancel
        await asyncio.gather(*current_tasks, return_exceptions=True)
        logging.info("All tasks completed/cancelled")
        logging.info("Graceful shutdown completed.")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
