from conversations.disentanglement_rule_based_classifier import rule_based_classifier
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
    # add from live run
    (
        {
            "lines": [
                {      
                    "seqid": 93720,
                    "ts": "2024-01-01T02:36:11.891062Z",
                    "user": "intelikey",
                    "message": "Works for me. Skype or Discord?"
                },
                {
                    "seqid": 93723,
                    "ts": "2024-01-01T02:36:12.191062Z",
                    "user": "Spiffyman",
                    "message": "intelikey: Sounds like fun. I may be joining you in that before long. When I get home from holiday break, I'll have to set up an old Apple LaserWriter."
                },
            ],
            "users": {"intelikey", "Spiffyman"},
            "last_updated": "2024-01-01T02:36:12.191062Z",
            "completed": False
        },
        {
            "seqid": 93909,
            "ts": "2024-01-01T02:36:30.791044Z",
            "user": "fdoving",
            "message": "you can make a uppercase command in bash too, if you want to."
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
