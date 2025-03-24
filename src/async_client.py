import asyncio
from datetime import datetime, timezone
import os
from pydantic import BaseModel
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError, InvalidURI
from calendar_event_classifier import is_calendar_event
from conversations.ops import disentangle_message, update_completed_conversation
from conversations.disentanglement_rule_based_classifier import rule_based_classifier
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
    state: AppState,  # Added state as a parameter
    classified_message_queue: asyncio.Queue, 
    state_update_queue: asyncio.Queue,
    active_conversations_metric
):
    while True:
        classified_message = await classified_message_queue.get()

        confident_it_is_a_calendar_event = (
            classified_message.classification.label == "LABEL_1"
            and classified_message.classification.score > 0.8
        )

        if confident_it_is_a_calendar_event:
            # Emit the message to the state update queue instead of modifying state directly
            await state_update_queue.put(classified_message)

        current_active = len(state.conversations)
        active_conversations_metric.n = current_active  # Set exact count
        active_conversations_metric.refresh()  


async def state_manager(state: AppState, state_update_queue: asyncio.Queue):
    while True:
        message = await state_update_queue.get()
        try:
            # Use existing disentanglement logic to update state
            state.conversations = disentangle_message(
                state.conversations,
                message,
                rule_based_classifier
            )
            state_update_queue.task_done()
        except Exception as e:
            logger.error(f"State update failed: {e}")
            state_update_queue.task_done()


async def archive_completed_conversations(
    conversation_archival_queue: asyncio.Queue, state: AppState
):
    while True:
        await asyncio.sleep(20)
        updated_convs = update_completed_conversation(
            state.conversations,
            seconds_lapsed=20,
            current_time=datetime.now(timezone.utc),
        )
        for conv in updated_convs:
            if conv.completed:
                await conversation_archival_queue.put(conv)

        state.conversations = [conv for conv in updated_convs if not conv.completed]
        asyncio.sleep(10)


async def listen(url, valid_message_queue: asyncio.Queue, messages_received):
    async with websockets.connect(url) as websocket:
        while True:
            message_data = await websocket.recv()
            message = Message.model_validate_json(message_data)
            await valid_message_queue.put(message)
            messages_received.update(1)  # Increment on each received message


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
    state_update_queue = asyncio.Queue()  # Added

    tasks = [
        listen(os.getenv("WS_SOCK"), valid_message_queue, metrics['messages_received']),
        classify_message(valid_message_queue, classified_message_queue, metrics['processed_messages']),
        match_conversation(state, classified_message_queue, state_update_queue, metrics['active_conversations']),  # Updated
        archive_completed_conversations(conversation_archival_queue, state),
        store_probable_calendar_conversations(conversation_archival_queue),
        state_manager(state, state_update_queue)  # Added
    ]
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except (KeyboardInterrupt, ConnectionClosedOK) as e:
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
            state_update_queue  # Added
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
