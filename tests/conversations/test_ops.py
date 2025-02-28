from datetime import datetime, timedelta, timezone
from conversations.ops import add_message_to_conversation, update_completed_conversation
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
    assert updated_conv.last_updated == ts


# Test updating a completed conversation
def test_update_marks_only_old_conversations_as_completed():
    current_time = datetime.now(timezone.utc)
    current_conv = Conversation(last_updated=current_time)
    slightly_old_conv = Conversation(last_updated=current_time - timedelta(seconds=10))
    older_conv = Conversation(last_updated=current_time - timedelta(seconds=40))
    conversations = [current_conv, slightly_old_conv, older_conv]

    updated_conversations = update_completed_conversation(conversations, 30)

    older_conv.completed = True
    assert updated_conversations == [current_conv, slightly_old_conv, older_conv]


