from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from client import AppState, extract_calendar_datetime_from_conversations, mark_completed_conversations, mark_suspended_conversations
from datatypes import CalendarClassification, ClassifiedMessage, Conversation


def create_classified_message(ts: datetime) -> ClassifiedMessage:
    return ClassifiedMessage(
        seqid=1,
        ts=ts,
        user="user1",
        message="test message",
        classification=CalendarClassification(label="LABEL_1", score=0.9)
    )


def create_conversation(messages: list[ClassifiedMessage], suspended=False, completed=False) -> Conversation:
    return Conversation(
        lines=messages,
        users={msg.user for msg in messages},
        last_updated=max(msg.ts for msg in messages) if messages else None,
        suspended=suspended,
        completed=completed
    )


def test_mark_suspended_conversations():
    current_time = datetime.now(timezone.utc)
    past_time = current_time - timedelta(seconds=40)  # older than 30 seconds

    msg_past = create_classified_message("LABEL_1", past_time)
    msg_now = create_classified_message("LABEL_1", current_time)

    conv_old = create_conversation([msg_past], suspended=False, completed=False)
    conv_new = create_conversation([msg_now], suspended=False, completed=False)

    state = AppState(calender_conversations=[conv_old, conv_new])

    updated_state = mark_suspended_conversations(state)
    
    assert len(updated_state.calender_conversations) == 2
    assert updated_state.calender_conversations[0].suspended == True
    assert updated_state.calender_conversations[1].suspended == False


def test_mark_completed_conversations_with_old_event_dates():
    current_time = datetime.now(timezone.utc)
    past_time = current_time - timedelta(days=1)  # older than a day

    msg_past = create_classified_message("LABEL_0", past_time)
    msg_now = create_classified_message("LABEL_0", current_time)

    conv_old = create_conversation([msg_past], suspended=True, completed=False)
    conv_new = create_conversation([msg_now], suspended=True, completed=False)

    state = AppState(calender_conversations=[conv_old, conv_new])

    updated_state = mark_completed_conversations(state)
    
    assert len(updated_state.calender_conversations) == 2
    assert updated_state.calender_conversations[0].completed == True
    assert updated_state.calender_conversations[1].completed == False


def mock_event_datetime_extractor(_conversation):
    return datetime.now(timezone.utc)


def test_extract_calendar_datetime_from_conversations_extracts_only_for_suspended_conversations(monkeypatch):
    current_time = datetime.now(timezone.utc)
    msg = create_classified_message("LABEL_1", current_time)

    conv_suspended = create_conversation([msg], suspended=True, completed=False)
    conv_not_suspended = create_conversation([msg], suspended=False, completed=False)

    state = AppState(calender_conversations=[conv_suspended, conv_not_suspended])

    monkeypatch.setattr('src.client.event_datetime_extractor', mock_event_datetime_extractor)

    updated_state = extract_calendar_datetime_from_conversations(state)
    
    assert len(updated_state.calender_conversations) == 2
    assert updated_state.calender_conversations[0].event_datetime is not None
    assert updated_state.calender_conversations[1].event_datetime is None