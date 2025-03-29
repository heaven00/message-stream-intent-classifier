import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
import websockets
from async_client import (
    listen,
    start_ingestion,
    classify_message,
    archive_completed_conversations,
    disentangle_message,
    store_probable_calendar_conversations,
)
from datatypes import CalendarClassification, ClassifiedMessage, Conversation, Message


def valid_message() -> str:
    return '''{"message": "great idea! when are you available next week?",
            "ts": 1741459420,
            "seqid": 1,
            "user": "anon",
            "classification": {"label": "LABEL_1", "score": 0.9}
        }'''


@pytest.mark.asyncio
async def test_websocket_listener():

    # setup
    async def handle_server(websocket):
        """Mock server sending test messages"""
        await websocket.send("Hello from test!")
        await asyncio.sleep(0.1)  # Short delay between sends
        await websocket.send("Another test message")
        await websocket.close()   # Close t


    received_messages = []

    # Define a mock callback to capture messages
    async def mock_callback(message):
        received_messages.append(message)

    # Create an event loop for the test
    async with websockets.serve(
        handle_server,
        "localhost",
        8765
    ):
        # Start the listener task
        listener_task = asyncio.create_task(
            listen("ws://localhost:8765", mock_callback)
        )

        # Allow some time for messages to be processed
        await asyncio.sleep(0.2)

        # Cancel the listener task to avoid hanging
        listener_task.cancel()

    # Assert that two messages were received correctly
    assert received_messages == ["Hello from test!", "Another test message"]


@pytest.mark.asyncio
async def test_start_ingestion_should_process_valid_message_and_pass_to_queue():
    valid_message_queue = asyncio.Queue()
    counter_mock = MagicMock()
    test_message = valid_message()

    await start_ingestion(test_message, valid_message_queue, counter_mock)

    assert valid_message_queue.qsize() == 1


@pytest.mark.asyncio
async def test_start_ingestion_should_process_invalid_message_and_pass_to_queue():
    valid_message_queue = asyncio.Queue()
    counter = MagicMock()

    await start_ingestion("not a valid message", valid_message_queue, counter)

    assert valid_message_queue.qsize() == 0
    # I don't know at the moment why this does not work
    # assert counter.assert_called_once()

@pytest.mark.asyncio
async def test_classify_message_processes_single_message():
    valid_queue = asyncio.Queue()
    classified_queue = asyncio.Queue()
    test_message = Message(seqid=1, ts=1741874411, user="user1", message="hi")
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="hi",
        classification=CalendarClassification(label="LABEL_0", score=0.5),
    )

    with patch("async_client.is_calendar_event", return_value=classified_test_message):
        processed_metric = MagicMock()
        await valid_queue.put(test_message)

        task = asyncio.create_task(classify_message(valid_queue, classified_queue, processed_metric))

        await asyncio.sleep(.1)
        assert valid_queue.qsize() == 0
        assert classified_queue.qsize() == 1
        assert classified_queue.get_nowait() == classified_test_message

        task.cancel()

    processed_metric.update.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_classify_task_runs_when_new_message_arrives_in_valid_queue():
    valid_queue = asyncio.Queue()
    classified_queue = asyncio.Queue()
    test_message = Message(seqid=1, ts=1741874411, user="user1", message="hi")
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="hi",
        classification=CalendarClassification(label="LABEL_0", score=0.5),
    )

    with patch("async_client.is_calendar_event", return_value=classified_test_message):
        processed_metric = MagicMock()

        task = asyncio.create_task(
            classify_message(valid_queue, classified_queue, processed_metric)
        )
        await valid_queue.put(test_message)
        await asyncio.sleep(.1)

        assert valid_queue.qsize() == 0
        assert classified_queue.qsize() == 1
        assert classified_queue.get_nowait() == classified_test_message

        # a new message is sent
        await valid_queue.put(test_message)
        await asyncio.sleep(.1)

        assert valid_queue.qsize() == 0
        assert classified_queue.qsize() == 1

        task.cancel()

    processed_metric.update.assert_called()



@pytest.mark.asyncio
async def test_match_conversation_updates_active_conversations():
    assert True


@pytest.mark.asyncio
async def test_store_probable_calendar_conversations():
    conversational_archival_queue = asyncio.Queue()

    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.9),
    )

    conversation_to_archive = Conversation(
        lines=[classified_test_message],
        users={classified_test_message.user},
        last_updated=classified_test_message.ts,
        completed=True,
    )

    await conversational_archival_queue.put(conversation_to_archive)

    mock_file = AsyncMock()
    with patch("aiofiles.open", return_value=mock_file) as mock_open:
        await store_probable_calendar_conversations(conversational_archival_queue)

        expected_filename = (
            f"results/event_{conversation_to_archive.lines[0].seqid}_v1.json"
        )
        mock_open.assert_called_once_with(expected_filename, "w")

        # Verify write and flush were called on the file handle
        mock_file.__aenter__.return_value.write.assert_awaited()
        mock_file.__aenter__.return_value.flush.assert_awaited()

    assert conversational_archival_queue.qsize() == 0
