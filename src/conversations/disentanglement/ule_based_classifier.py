import re
from typing import Callable

from pydantic import BaseModel
from datatypes import Conversation, ClassifiedMessage
from sentence_transformers import SentenceTransformer, util
import numpy as np


# convert to a class to load the model only when needed
model_name = "sentence-transformers/all-mpnet-base-v2"
model = SentenceTransformer(model_name)


# Time-based Clustering
def is_within_time_window(
    conversation: Conversation, message: ClassifiedMessage
) -> float:
    elapsed_seconds = (message.ts - conversation.lines[-1].ts).total_seconds()
    max_elapsed_time = 30.0

    if elapsed_seconds >= max_elapsed_time:
        return 0

    return (max_elapsed_time - elapsed_seconds) / max_elapsed_time


# Keyword Matching
def has_matching_keywords(
    conversation: Conversation, message: ClassifiedMessage
) -> float:
    # Extract keywords from the conversation
    all_text = " ".join([msg.message for msg in conversation.lines])
    keywords = set(re.findall(r"\b\w+\b", all_text.lower()))

    # Count occurrences of these keywords in the new message
    message_words = set(re.findall(r"\b\w+\b", message.message.lower()))
    common_keywords = keywords.intersection(message_words)

    if len(message_words) > 0:
        return len(common_keywords) / len(message_words)
    return 0.0


# User Interaction Patterns
def is_reply_to_conversation(
    conversation: Conversation, message: ClassifiedMessage
) -> float:
    # Check if the message mentions any user from the conversation
    pattern = re.compile(r"@(\w+)", re.IGNORECASE)
    mentioned_users = pattern.findall(message.message)
    return 1.0 if bool(set(mentioned_users) & conversation.users) else 0.0


def user_is_part_of_conversation(
    conversation: Conversation, message: ClassifiedMessage
) -> float:
    return 1.0 if message.user in conversation.users else 0.0


# Semantic Similarity
def semantic_similarity_score(
    conversation: Conversation, message: ClassifiedMessage, similarity_threshold=0.5
) -> float:
    def _generate_embedding(text: list[str]) -> np.ndarray:
        return model.encode(text, show_progress_bar=False, normalize_embeddings=True)

    # Generate embeddings for the conversation and the new message
    conversation_embeddings = _generate_embedding(
        "\n".join([msg.message for msg in conversation.lines])
    )
    message_embedding = _generate_embedding(message.message)

    return util.dot_score(conversation_embeddings, message_embedding)[0][0]


class Rule(BaseModel):
    function: Callable[[Conversation, ClassifiedMessage], float]
    weight: float
    name: str


def execute_rules(
    conversation: Conversation, message: ClassifiedMessage, rules: list[Rule]
) -> dict[str, float]:
    """
    Apply a list of rules to a message and return a mapping of rule names to their weighted scores.

    Args:
        conversation (Conversation): The conversation context.
        message (Message): The new message to classify.
        rules (List[Rule]): A list of Rule instances.

    Returns:
        Dict[str, float]: A dictionary mapping rule names to their weighted scores.
    """
    scores = {}
    for rule in rules:
        # Compute the score from the rule function and apply the weight
        raw_score = rule.function(conversation, message)
        weighted_score = raw_score * rule.weight
        scores[rule.name] = weighted_score
    return scores


def rule_based_classifier(
    conversation: Conversation, message: ClassifiedMessage
) -> bool:
    rule_book: list[Rule] = [
        Rule(name="is_within_time_window", function=is_within_time_window, weight=1.0),
        Rule(name="reply_detection", function=is_reply_to_conversation, weight=1.0),
        Rule(
            name="user_in_conversation",
            function=user_is_part_of_conversation,
            weight=1.0,
        ),
        Rule(
            name="semantic_similarity", function=semantic_similarity_score, weight=0.7
        )
    ]

    scores = execute_rules(conversation, message, rule_book)
    return any(
        [
            scores["reply_detection"] == 1.0,
            (scores["semantic_similarity"] > 0.6) and (scores["is_within_time_window"] < 30),
            scores["user_in_conversation"]  and (scores["is_within_time_window"] < 5)
        ]
    )
