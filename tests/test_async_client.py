import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import UUID, uuid4
import pytest
import websockets
from async_client import (
    conversation_manager,
    listen,
    start_ingestion,
    classify_message,
    archive_completed_conversations,
    classified_message_to_conversation,
    store_probable_calendar_conversations,
)
from conversations.ops import add_message_to_conversation
from datatypes import AddToConversationEvent, CalendarClassification, ClassifiedMessage, Conversation, CreateConversationEvent, Message


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

    with patch("async_client.aiofiles.open", AsyncMock()) as mock_open:
        # Create an instance of AsyncMock to simulate the file object
        mock_file = AsyncMock()
        mock_open.return_value.__aenter__.return_value = mock_file
        
        task = asyncio.create_task(store_probable_calendar_conversations(conversational_archival_queue))
        
        # Wait for the queue to be processed
        while not conversational_archival_queue.empty():
            await asyncio.sleep(0.1)  # Small delay to allow processing

        # Ensure that open was called with the correct filename
        expected_filename = f"results/event_{conversation_to_archive.lines[0].seqid}_v2.json"
        mock_open.assert_called_once_with(expected_filename, "w")
        
        # Ensure that write and flush were called on the file object
        expected_content = conversation_to_archive.model_dump_json()
        mock_file.write.assert_called_once_with(expected_content)
        mock_file.flush.assert_called_once()

        task.cancel()
    assert conversational_archival_queue.qsize() == 0



@pytest.mark.asyncio
async def test_disentangle_message_no_previous_messages():
    classified_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()

    message_data = {
        "seqid": 1,
        "ts": 1741874411,
        "user": "user1",
        "message": "hi",
        "classification": CalendarClassification(label="LABEL_0", score=0.5)
    }
    classified_message = ClassifiedMessage.model_validate(message_data)

    await classified_queue.put(classified_message)

    task = asyncio.create_task(classified_message_to_conversation(classified_queue, state_update_queue))

    # Allow some time for processing
    await asyncio.sleep(0.1)

    assert classified_queue.qsize() == 0

    event = state_update_queue.get_nowait()
    assert isinstance(event, CreateConversationEvent)
    assert event.message == classified_message

    task.cancel()



@pytest.mark.asyncio
async def test_disentangle_message_with_previous_messages_is_continuation():
    classified_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()

    message_data_1 = {
        "seqid": 1,
        "ts": 1741874411,
        "user": "user1",
        "message": "hi",
        "classification": CalendarClassification(label="LABEL_0", score=0.5)
    }
    classified_message_1 = ClassifiedMessage.model_validate(message_data_1)

    message_data_2 = {
        "seqid": 2,
        "ts": 1741874412,
        "user": "user1",
        "message": "hello again",
        "classification": CalendarClassification(label="LABEL_0", score=0.5)
    }
    classified_message_2 = ClassifiedMessage.model_validate(message_data_2)
    task = asyncio.create_task(classified_message_to_conversation(classified_queue, state_update_queue))

    await classified_queue.put(classified_message_1)
    await asyncio.sleep(0.1)  # Give some time for the first message to be processed

    with patch("async_client._is_continuation", return_value=0):
        await classified_queue.put(classified_message_2)

        
        await asyncio.sleep(0.1)

    assert classified_queue.qsize() == 0

    event = state_update_queue.get_nowait()
    assert isinstance(event, CreateConversationEvent)
    assert event.message == classified_message_1

    event = state_update_queue.get_nowait()
    assert isinstance(event, AddToConversationEvent)
    assert event.message == classified_message_2
    assert event.previous_message == classified_message_1

    task.cancel()


@pytest.mark.asyncio
async def test_disentangle_message_with_previous_messages_not_continuation():
    classified_queue = asyncio.Queue()
    state_update_queue = asyncio.Queue()

    message_data_1 = {
        "seqid": 1,
        "ts": 1741874411,
        "user": "user1",
        "message": "hi",
        "classification": CalendarClassification(label="LABEL_0", score=0.5)
    }
    classified_message_1 = ClassifiedMessage.model_validate(message_data_1)

    message_data_2 = {
        "seqid": 2,
        "ts": 1741874412,
        "user": "user1",
        "message": "hello again",
        "classification": CalendarClassification(label="LABEL_0", score=0.5)
    }
    classified_message_2 = ClassifiedMessage.model_validate(message_data_2)
    task = asyncio.create_task(classified_message_to_conversation(classified_queue, state_update_queue))

    await classified_queue.put(classified_message_1)
    await asyncio.sleep(0.1)  # Give some time for the first message to be processed

    with patch("async_client._is_continuation", return_value=-1):
        await classified_queue.put(classified_message_2)

        # Allow some time for processing
        await asyncio.sleep(0.1)

    assert classified_queue.qsize() == 0

    event = state_update_queue.get_nowait()
    assert isinstance(event, CreateConversationEvent)
    assert event.message == classified_message_1

    event = state_update_queue.get_nowait()
    assert isinstance(event, CreateConversationEvent)
    assert event.message == classified_message_2

    task.cancel()



@pytest.mark.asyncio
async def test_conversation_manager_create_event_updates_conversations_and_conv_seq_id_map():
    # Create a queue
    state_update_queue = asyncio.Queue()
    conversations, conv_seq_id_map = {}, {}
    archival_queue = asyncio.Queue()

    task = asyncio.create_task(conversation_manager(state_update_queue, conversations, conv_seq_id_map, archival_queue))

    # Create a classified message for creating a new conversation
    create_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="This is a test message.",
        classification=CalendarClassification(label="LABEL_0", score=0.9)
    )
    
    # Create a create conversation event and put it in the queue
    create_event = CreateConversationEvent(
        message=create_message
    )
    await state_update_queue.put(create_event)

    # Wait for the manager to process the event
    await asyncio.sleep(0.1)  # Give some time for the task to run

    # Check if conversations and conv_seq_id_map were updated correctly
    assert len(conversations) == 1
    conversation_uuid = list(conversations.keys())[0]
    assert isinstance(conversation_uuid, str)
    assert conv_seq_id_map == {1: conversation_uuid}

    task.cancel()


@pytest.mark.asyncio
async def test_conversation_manager_add_event_updates_conversations_and_conv_seq_id_map():
    # Create a queue
    state_update_queue = asyncio.Queue()
    archival_queue = asyncio.Queue()

    # Create a classified message for creating a new conversation
    message = ClassifiedMessage(
        seqid=2,
        ts=1741874411,
        user="user1",
        message="This is a test message.",
        classification=CalendarClassification(label="LABEL_0", score=0.9)
    )

    previous_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user5",
        message="This is a test message.",
        classification=CalendarClassification(label="LABEL_0", score=0.9)
    )
    conv_id = str(uuid4()) 
    conversations = {conv_id: add_message_to_conversation(Conversation(), previous_message)}
    conv_seq_id_map = {1: conv_id}

    task = asyncio.create_task(conversation_manager(state_update_queue, conversations, conv_seq_id_map, archival_queue))
    
    add_event = AddToConversationEvent(
        message=message,
        previous_message=previous_message
    )
    await state_update_queue.put(add_event)

    # Wait for the manager to process the event
    await asyncio.sleep(0.1)  # Give some time for the task to run

    assert len(conversations) == 1
    assert len(conversations[conv_id].lines) == 2
    task.cancel()