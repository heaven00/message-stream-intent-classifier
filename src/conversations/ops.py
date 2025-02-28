from datatypes import Conversation, ClassifiedMessage
from typing import Callable
from datetime import datetime, timezone


def add_message_to_conversation(conversation: Conversation, message: ClassifiedMessage):
    conversation.lines.append(message)
    conversation.users.add(message.user)
    conversation.last_updated = message.ts
    return conversation


def update_completed_conversation(
    conversations: list[Conversation], seconds_lapsed: int
) -> list[Conversation]:
    """Discard conversations older than seconds lapsed parameter"""
    current_time = datetime.now(timezone.utc)
    for conv in conversations:
        if (current_time - conv.last_updated).total_seconds() <= seconds_lapsed:
            conv.completed = True
    return conversations


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
            updates.append(add_message_to_conversation(conversation, message))
            matched = True
        else:
            updates.append(conversation)
    if not matched:
        updates.append(Conversation(lines=[message], last_updated=message.ts))
    return updates
