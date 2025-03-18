import logging
logger = logging.getLogger(__name__)

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
    updates = []
    matched = False
    for conversation in conversations:
        if classifier(conversation, message):
            logger.debug(f"Matched to existing conversation. Current lines: {', '.join([msg.message for msg in conversation.lines[:-2]])}")
            updates.append(add_message_to_conversation(conversation, message))
            matched = True
        else:
            updates.append(conversation)
    if not matched:
        logger.debug(f"No match found for message: '{message.message}'")
        new_conv = Conversation()
        updates.append(
            add_message_to_conversation(new_conv, message)
        )
    return updates
