import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from websockets import ConnectionClosedOK
from async_client import AppState, classify_message, listen, match_conversation
from datatypes import CalendarClassification, ClassifiedMessage, Message


@pytest.mark.asyncio
async def test_listen_sends_valid_message_to_provided_queue():
    url = "ws://some-url"
    mock_ws = AsyncMock()
    json_message = '{"seqid": 1, "ts": 1741874411, "user": "user1", "message": "hi"}'
    mock_ws.recv.return_value = json_message

    valid_queue = asyncio.Queue()
    mock_connection = AsyncMock(return_value=mock_ws)

    with patch('websockets.connect', side_effect=mock_connection):
        task = asyncio.create_task(listen(url, valid_queue))

        await asyncio.sleep(0.1)  # Use await for proper async sleep
        assert mock_connection.called
        assert mock_ws.recv.called
        assert valid_queue.qsize() == 1

        assert valid_queue.get_nowait() == Message.model_validate_json(json_message)

        mock_ws.close.side_effect = ConnectionClosedOK(
            rcvd={'code': 1000, 'reason': 'OK'},
            sent=None)
        await task


@pytest.mark.asyncio
async def test_classify_message_queue_normal_flow():
    # Setup
    valid_queue = asyncio.Queue()
    classified_queue = asyncio.Queue()
    test_message = Message(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="hi"
    )
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="hi",
        classification=CalendarClassification(label='LABEL_0', score=0.5)
    )
        
    # Patch the classification function
    with patch('async_client.is_calendar_event', return_value=classified_test_message):
        await valid_queue.put(test_message)
        await asyncio.sleep(0.1)
        
        task = asyncio.create_task(classify_message(valid_queue, classified_queue))
        
        await asyncio.sleep(0.1)

        task.cancel()

        # Verify
        assert valid_queue.qsize() == 0
        assert classified_queue.qsize() == 1
        assert classified_queue.get_nowait() == classified_test_message 


@pytest.mark.asyncio
async def test_match_conversation_queue_normal_flow_with_confident_message():
    # Setup
    state = AppState()

    classified_queue = asyncio.Queue()
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label='LABEL_1', score=0.9)
    )
        
    # Patch the classification function
    with patch('async_client.is_calendar_event', return_value=classified_test_message):
        await classified_queue.put(classified_test_message)
        await asyncio.sleep(0.1)
        
        task = asyncio.create_task(match_conversation(classified_queue, state))
        
        await asyncio.sleep(0.1)

        task.cancel()

        # Verify
        print(state, flush=True)
        assert classified_queue.qsize() == 0
        assert len(state.conversations) == 1


@pytest.mark.asyncio
async def test_match_conversation_queue_normal_flow_with_non_confident_message():
    # Setup
    state = AppState()

    classified_queue = asyncio.Queue()
    classified_test_message = ClassifiedMessage(
        seqid=1,
        ts=1741874411,
        user="user1",
        message="sharing google meet link",
        classification=CalendarClassification(label='LABEL_1', score=0.5)
    )
        
    # Patch the classification function
    with patch('async_client.is_calendar_event', return_value=classified_test_message):
        await classified_queue.put(classified_test_message)
        await asyncio.sleep(0.1)
        
        task = asyncio.create_task(match_conversation(classified_queue, state))
        
        await asyncio.sleep(0.1)

        task.cancel()

        # Verify
        assert classified_queue.qsize() == 0
        assert len(state.conversations) == 0
    