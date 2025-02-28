from conversations.disentanglement_classifier import rule_based_classifier
import pytest
from datetime import datetime, timedelta
from datatypes import Conversation, Message

# Fixed base datetime for tests
base_time = datetime(2025, 2, 28, 12, 0, 0)

@pytest.mark.parametrize("conversation_data, message_data, expected", [
    # Case 1: Positive classification.
    # A Slack-style conversation where the new message replies to the conversation by mentioning a user,
    # contains overlapping keywords, and is sent within the time window.
    (
        {
            "lines": [
                {
                    "seqid": 1,
                    "ts": base_time,
                    "user": "alice",
                    "message": "Hey team, meeting at 2pm in the conference room."
                },
                {
                    "seqid": 2,
                    "ts": base_time,
                    "user": "bob",
                    "message": "Got it. I'll bring the reports."
                },
            ],
            "users": {"alice", "bob"},
            "last_updated": base_time,
            "completed": False
        },
        {
            "seqid": 3,
            "ts": (base_time + timedelta(seconds=5)),
            "user": "charlie",
            "message": "Hi @alice, I’m joining the meeting at 2pm. Ready with my report."
        },
        True
    ),
    # Case 2: Negative classification.
    # An IRC-style conversation where the new message is off-topic (no keyword overlap, no proper mention)
    # even though it is sent promptly.
    (
        {
            "lines": [
                {
                    "seqid": 1,
                    "ts": base_time,
                    "user": "alice",
                    "message": "Reminder: our meeting is at 2pm in the main hall."
                },
                {
                    "seqid": 2,
                    "ts": base_time,
                    "user": "bob",
                    "message": "Please prepare your status updates."
                },
            ],
            "users": {"alice", "bob"},
            "last_updated": base_time,
            "completed": False
        },
        {
            "seqid": 4,
            "ts": (base_time + timedelta(seconds=5)),
            "user": "dave",
            "message": "Anyone up for lunch after work?"
        },
        False
    ),
    # Case 3: Borderline classification.
    # A conversation where the new message is sent very late (almost at the end of the time window),
    # has limited keyword overlap and no user mention. The delayed time reduces the score.
    (
        {
            "lines": [
                {
                    "seqid": 1,
                    "ts": base_time,
                    "user": "alice",
                    "message": "FYI, the quarterly report is now available."
                },
                {
                    "seqid": 2,
                    "ts": base_time,
                    "user": "bob",
                    "message": "Review the report before our next call."
                },
            ],
            "users": {"alice", "bob"},
            "last_updated": base_time,
            "completed": False
        },
        {
            "seqid": 5,
            "ts": (base_time + timedelta(seconds=29)),
            "user": "eve",
            "message": "The report looks interesting."
        },
        False
    ),
])
def test_rule_based_classifier(conversation_data, message_data, expected):
    # Instantiate our Pydantic models from the provided dictionaries.
    conversation = Conversation(**conversation_data)
    message = Message(**message_data)

    # Execute the classifier.
    result = rule_based_classifier(conversation, message)

    assert result == expected, f"Expected {expected} but got {result}"
