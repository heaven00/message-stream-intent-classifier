from datetime import datetime, timedelta, timezone
from conversations.disentanglement_classifier import has_matching_keywords, is_reply_to_conversation, is_within_time_window
from datatypes import Conversation, Message
import pytest


@pytest.mark.parametrize("elapsed_seconds, expected_score", [
    (0, 1),
    (15, 0.5),
    (30, 0),
    (50, 0)
])
def test_is_within_time_window_returns(elapsed_seconds, expected_score):
    start = datetime.now(tz=timezone.utc)
    conversation = Conversation(last_updated=start)
    message = Message(
        seqid=1, 
        ts=start + timedelta(seconds=elapsed_seconds),
        user="user",
        message="message")
    
    assert is_within_time_window(conversation, message) == expected_score



@pytest.mark.parametrize(
    "conversation_texts, new_message_text, expected_score",
    [
        (["hello world", "bye"], "hello", 1.0),
        (["hello world", "bar"], "foo", 0.0),
        (["did you head about the new model?"], "what model?", .5),
    ],
)
def test_has_matching_keywords(conversation_texts, new_message_text, expected_score):
    conversation = Conversation(lines=[message_from_text(text) for text in conversation_texts])
    new_message = message_from_text(new_message_text)
    
    score = has_matching_keywords(conversation, new_message)
    
    # Use a tolerance for floating point comparisons
    assert abs(score - expected_score) < 1e-6, f"Expected score {expected_score}, but got {score}"


# Parameterized tests
@pytest.mark.parametrize(
    "conversation_users, message, expected_score",
    [
        # Case 1: Message mentions a user in the conversation, should return 1.0
        ({"alice", "bob"}, "Hello @alice, how are you?", 1.0),

        # Case 2: Message mentions multiple users, one of which is in the conversation, should return 1.0
        ({"alice", "bob"}, "Hey @charlie and @bob, let's meet!", 1.0),

        # Case 3: Message mentions a user not in the conversation, should return 0.0
        ({"alice", "bob"}, "Good morning @charlie!", 0.0),

        # Case 4: Message has no mentions, should return 0.0
        ({"alice", "bob"}, "Hey everyone, what's up?", 0.0),

        # Case 5: Message contains a similar word but no proper mention (should still return 0.0)
        ({"alice", "bob"}, "That was an amazing alicetime!", 0.0),
    ],
)
def test_is_reply_to_conversation(conversation_users, message, expected_score):
    # Create a conversation with predefined users
    conversation = Conversation(users=conversation_users)

    # Create a message
    new_message = message_from_text(message)

    # Run the function
    score = is_reply_to_conversation(conversation, new_message)

    # Assert the expected score
    assert score == expected_score, f"Expected {expected_score}, but got {score}"


def message_from_text(text: str):
    return Message(seqid=1, ts=datetime.now(), user="test", message=text)
