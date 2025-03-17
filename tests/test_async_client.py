import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from websockets import ConnectionClosedOK
from async_client import (
    AppState,
    classify_message,
    archive_completed_conversations,
    flush_all_conversations,
    listen,
    match_conversation,
    store_probable_calendar_conversations,
)
from datatypes import CalendarClassification, ClassifiedMessage, Conversation, Message


@pytest.mark.asyncio
async def test_listen_sends_valid_message_to_provided_queue():
    url = "ws://some-url"
    mock_ws = AsyncMock()
    json_message = '{"seqid": 1, "ts": 1741874411, "user": "user1", "message": "hi"}'
    mock_ws.recv.return_value = json_message

    valid_queue = asyncio.Queue()
    messages_received_mock = MagicMock()
    mock_connection = AsyncMock(return_value=mock_ws)

    with patch("websockets.connect", side_effect=mock_connection):
        task = asyncio.create_task(listen(url, valid_queue, messages_received_mock))

        await asyncio.sleep(0.1)
        assert mock_connection.called
        assert mock_ws.recv.called
        assert valid_queue.qsize() == 1

        assert valid_queue.get_nowait() == Message.model_validate_json(json_message)

        mock_ws.close.side_effect = ConnectionClosedOK(
            rcvd={"code": 1000, "reason": "OK"}, sent=None
        )
        await task
        await asyncio.sleep(0.1)
        task.cancel()

    messages_received_mock.update.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_classify_message_queue_normal_flow():
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
        await valid_queue.put(test_message)
        await asyncio.sleep(0.1)

        processed_metric = MagicMock()
        task = asyncio.create_task(classify_message(valid_queue, classified_queue, processed_metric))

        await asyncio.sleep(0.1)

        task.cancel()

        assert valid_queue.qsize() == 0
        assert classified_queue.qsize() == 1
        assert classified_queue.get_nowait() == classified_test_message

    processed_metric.update.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_match_conversation_updates_active_conversations():
    state = AppState()
    active_mock = MagicMock()

    classified_queue = asyncio.Queue()  
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.9),
    )

    await classified_queue.put(classified_test_message)
    
    # Start the task
    task = asyncio.create_task(match_conversation(
        classified_queue, state, active_mock))
    
    # Wait briefly for processing (or use a condition to wait until queue is empty)
    await asyncio.sleep(0.1)  # Adjust timeout as needed
    
    # Cancel the task to prevent infinite loop
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(state.conversations) == 1
    assert active_mock.n == 1


@pytest.mark.asyncio
async def test_match_conversation_queue_normal_flow_with_confident_message():
    state = AppState()
    active_mock = MagicMock()  # Add this line

    classified_queue = asyncio.Queue()  
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.9),
    )

    with patch("async_client.is_calendar_event", return_value=classified_test_message):
        await classified_queue.put(classified_test_message)
        await asyncio.sleep(0.1)

        task = asyncio.create_task(match_conversation(
            classified_queue, state, active_mock))  # Add active_mock here
        await task
        await asyncio.sleep(0.1)

        task.cancel()

        assert classified_queue.qsize() == 0
        assert len(state.conversations) == 1


@pytest.mark.asyncio
async def test_match_conversation_queue_normal_flow_with_non_confident_message():
    state = AppState()
    active_mock = MagicMock()  # Add this line

    classified_queue = asyncio.Queue()  
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.5),
    )

    with patch("async_client.is_calendar_event", return_value=classified_test_message):
        await classified_queue.put(classified_test_message)
        await asyncio.sleep(0.1)

        task = asyncio.create_task(match_conversation(
            classified_queue, state, active_mock))  # Add active_mock here
        await task
        await asyncio.sleep(0.1)

        task.cancel()

        assert classified_queue.qsize() == 0
        assert len(state.conversations) == 0


@pytest.mark.asyncio
async def test_completed_conversation_archives_completed_converstaions():
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.5),
    )
    completed_conversation = Conversation(
        lines=[classified_test_message],
        users={
            classified_test_message.user,
        },
        last_updated=classified_test_message.ts,
        completed=True,
    )

    state = AppState(conversations=[completed_conversation])

    archival_queue = asyncio.Queue()
    task = asyncio.create_task(archive_completed_conversations(archival_queue, state))
    await task
    await asyncio.sleep(0.1)

    task.cancel()

    assert archival_queue.qsize() == 1
    assert await archival_queue.get() == completed_conversation


@pytest.mark.asyncio
async def test_flush_all_conversation_archives_all_converstaions():
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label="LABEL_1", score=0.5),
    )
    completed_conversation = Conversation(
        lines=[classified_test_message],
        users={
            classified_test_message.user,
        },
        last_updated=classified_test_message.ts,
        completed=True,
    )
    incomplete_conversation = Conversation(
        lines=[classified_test_message],
        users={
            classified_test_message.user,
        },
        last_updated=classified_test_message.ts,
        completed=False,
    )

    state = AppState(conversations=[completed_conversation, incomplete_conversation])

    archival_queue = asyncio.Queue()
    task = asyncio.create_task(flush_all_conversations(archival_queue, state))
    await task
    await asyncio.sleep(0.1)

    task.cancel()

    assert archival_queue.qsize() == 2


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
