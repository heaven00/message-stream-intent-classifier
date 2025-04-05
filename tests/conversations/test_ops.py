from datetime import datetime, timedelta, timezone

from pytz import UTC
from conversations.ops import add_message_to_conversation, update_completed_conversation, update_suspended_conversation
from datatypes import Conversation, ClassifiedMessage, CalendarClassification


# Test adding a message to a conversation
def test_add_message_to_conversation():
    conv = Conversation()
    ts = datetime.now(timezone.utc)
    msg = ClassifiedMessage(
        seqid=1,
        ts=ts,
        user="user1",
        message="hello",
        classification=CalendarClassification(label="LABEL_0", score=.9)
    )

    updated_conv = add_message_to_conversation(conv, msg)

    assert len(updated_conv.lines) == 1
    assert updated_conv.lines[0].seqid == 1
    assert updated_conv.users == {"user1"}
    assert updated_conv.last_updated > ts


# Test updating a completed conversation
def test_update_marks_only_old_conversations_as_completed():
    current_time = datetime(2024, 1, 2, 8, 59, 37, 286725, tzinfo=UTC)
    current_conv = Conversation(last_updated=current_time)
    slightly_old_conv = Conversation(last_updated=current_time - timedelta(seconds=10))
    older_conv = Conversation(last_updated=current_time - timedelta(seconds=40))
    conversations = [current_conv, slightly_old_conv, older_conv]

    updated_conversations = update_suspended_conversation(conversations, 30, current_time)

    assert [conv.suspended for conv in updated_conversations] == [False, False, True]


def test_update_completed_conversation():
    # Create some sample data
    past_datetime = datetime.now() - timedelta(days=1)
    future_datetime = datetime.now() + timedelta(days=1)

    conversation1 = Conversation(
        event_datetime=past_datetime,
        lines=[],
        users=set(),
        last_updated=None,
        suspended=False,
        completed=False
    )

    conversation2 = Conversation(
        event_datetime=future_datetime,
        lines=[],
        users=set(),
        last_updated=None,
        suspended=False,
        completed=False
    )

    conversation3 = Conversation(
        event_datetime=None,
        lines=[],
        users=set(),
        last_updated=None,
        suspended=False,
        completed=False
    )

    conversations = [conversation1, conversation2, conversation3]

    # Call the function with a current time in between past and future datetime
    updated_conversations = update_completed_conversation(conversations, datetime.now())

    # Check that the completed status is correctly set
    assert updated_conversations[0].completed == True, "Conversation 1 should be marked as completed"
    assert updated_conversations[1].completed == False, "Conversation 2 should not be marked as completed"
    assert updated_conversations[1].completed == False, "Conversation 2 should remain unchanged"
