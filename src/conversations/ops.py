from datatypes import Conversation, ClassifiedMessage
from typing import Callable
from datetime import datetime, timedelta, timezone


def add_message_to_conversation(conversation: Conversation, message: ClassifiedMessage):
    conversation.lines.append(message)
    conversation.users.add(message.user)
    conversation.last_updated = datetime.now(timezone.utc)
    return conversation


def update_completed_conversation(
    conversations: list[Conversation], seconds_lapsed: int, current_time: datetime
) -> list[Conversation]:
    """Discard conversations older than seconds lapsed parameter"""
    updated_conversations = []
    for conv in conversations:
        time_diff = (current_time - conv.last_updated)
        if  time_diff > timedelta(seconds=seconds_lapsed):
            conv.completed = True
        updated_conversations.append(conv)
    return updated_conversations


def disentangle_message(
    conversations: list[Conversation],
    message: ClassifiedMessage,
    classifier: Callable[[Conversation, ClassifiedMessage], bool],
) -> list[Conversation]:
    """Compare with all the existing conversations to see if the message is
    part of the existing one or
    """
    updates = []
    matched = False
    for conversation in conversations:
        if classifier(conversation, message):
            print("matched to existing conversation")
            print("Conversation:", ', '.join([msg.message for msg in conversation.lines[:-2]]))
            updates.append(add_message_to_conversation(conversation, message))
            matched = True
        else:
            updates.append(conversation)
    if not matched:
        print("did not match to any conversations")
        updates.append(
            add_message_to_conversation(Conversation(), message)
        )
    return updates
