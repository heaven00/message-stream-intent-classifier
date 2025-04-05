from datetime import UTC, datetime, timedelta, timezone
from conversations.disentanglement.rule_based_classifier import (
    has_matching_keywords,
    is_reply_to_conversation,
    is_within_time_window,
)
from datatypes import CalendarClassification, ClassifiedMessage, Conversation, Message
import pytest


@pytest.mark.parametrize(
    "elapsed_seconds, expected_score", [(0, 1), (15, 0.5), (30, 0), (50, 0)]
)
def test_is_within_time_window_returns(elapsed_seconds, expected_score):
    start = datetime.now(tz=timezone.utc)
    conversation = Conversation(
        lines=[
            ClassifiedMessage(
                seqid=1,
                ts=start,
                user="test",
                message="test",
                classification=CalendarClassification(label="LABEL_1", score=0.8),
            )
        ]
    )
    message = Message(
        seqid=2,
        ts=start + timedelta(seconds=elapsed_seconds),
        user="user",
        message="message",
    )

    assert is_within_time_window(conversation, message) == expected_score


@pytest.mark.parametrize(
    "conversation_texts, new_message_text, expected_score",
    [
        (["hello world", "bye"], "hello", 1.0),
        (["hello world", "bar"], "foo", 0.0),
        (["did you head about the new model?"], "what model?", 0.5),
    ],
)
def test_has_matching_keywords(conversation_texts, new_message_text, expected_score):
    conversation = Conversation(
        lines=[message_from_text(text) for text in conversation_texts]
    )
    new_message = message_from_text(new_message_text)

    score = has_matching_keywords(conversation, new_message)

    # Use a tolerance for floating point comparisons
    assert (
        abs(score - expected_score) < 1e-6
    ), f"Expected score {expected_score}, but got {score}"


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


def test_failing_is_time_within_scenario():
    conversation = Conversation(
        lines=[
            ClassifiedMessage(
                seqid=99686,
                ts=datetime(2024, 1, 1, 2, 46, 8, 490493, tzinfo=UTC),
                user="CoJaBo-Aztec",
                message="robin____: Anything else I need to do? I tried browsing the shares of the computer that has the printer, but nothing is listed.",
                classification=CalendarClassification(
                    label="LABEL_1", score=0.8196368217468262
                ),
            ),
            ClassifiedMessage(
                seqid=99795,
                ts=datetime(2024, 1, 1, 2, 46, 19, 390483, tzinfo=UTC),
                user="genii",
                message="SilentSound: Probably not at this stage. You can run the memtest anytime after as well. It takes quite a while to get some kind of reliable result from it, usually 12 hours or more is good.",
                classification=CalendarClassification(
                    label="LABEL_1", score=0.8096779584884644
                ),
            ),
            ClassifiedMessage(
                seqid=99865,
                ts=datetime(2024, 1, 1, 2, 46, 26, 390476, tzinfo=UTC),
                user="_Whipper",
                message="cool, google meet work for everyone?",
                classification=CalendarClassification(
                    label="LABEL_1", score=0.8699706792831421
                ),
            ),
            ClassifiedMessage(
                seqid=99867,
                ts=datetime(2024, 1, 1, 2, 46, 26, 590476, tzinfo=UTC),
                user="_Whipper",
                message="how about tomorrow 1900 UTC?",
                classification=CalendarClassification(
                    label="LABEL_1", score=0.8925792574882507
                ),
            ),
        ],
        users={"CoJaBo-Aztec", "genii", "_Whipper"},
        last_updated=datetime(2025, 4, 2, 12, 39, 44, 182970, tzinfo=UTC),
        suspended=False,
    )
    message = ClassifiedMessage(
        seqid=99966,
        ts=datetime(2024, 1, 1, 2, 46, 36, 490467, tzinfo=UTC),
        user="neversfelde",
        message="well, that are at least two things :). You should specifiy your problem a bit?",
        classification=CalendarClassification(
            label="LABEL_1", score=0.8237484693527222
        ),
    )
    assert is_within_time_window(conversation, message) == pytest.approx(0.67, 0.68)                                                                
