from datetime import timedelta, datetime
import re
from typing import List, Callable, Optional
from datatypes import Conversation, Message
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np


model_name = "sentence-transformers/all-MiniLM-L6-v2"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)


def generate_embedding(text: str) -> np.ndarray:
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )
    with torch.no_grad():
        outputs = model(**inputs)
    # Use the [CLS] token's hidden state as the sentence embedding
    cls_embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()
    return cls_embedding


def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


# Time-based Clustering
def is_within_time_window(
    conversation: Conversation, message: Message, time_window=timedelta(minutes=10)
) -> float:
    return 1.0 if (message.timestamp - conversation.last_updated) <= time_window else 0.0


# Keyword Matching
def has_matching_keywords(
    conversation: Conversation, message: Message, keyword_threshold=2
) -> float:
    # Extract keywords from the conversation
    all_text = " ".join([msg.text for msg in conversation.lines])
    keywords = set(re.findall(r"\b\w+\b", all_text.lower()))

    # Count occurrences of these keywords in the new message
    message_words = set(re.findall(r"\b\w+\b", message.text.lower()))
    common_keywords = keywords.intersection(message_words)

    return (
        len(common_keywords) / keyword_threshold
        if len(common_keywords) >= keyword_threshold
        else 0.0
    )


# User Interaction Patterns
def is_reply_to_conversation(conversation: Conversation, message: Message) -> float:
    # Check if the message mentions any user from the conversation
    users = set(msg.user for msg in conversation.lines)
    pattern = re.compile(r"@(\w+)", re.IGNORECASE)
    mentioned_users = pattern.findall(message.text)

    return 1.0 if bool(set(mentioned_users) & users) else 0.0


# Semantic Similarity
def semantic_similarity_score(
    conversation: Conversation, message: Message, similarity_threshold=0.5
) -> float:
    # Generate embeddings for the conversation and the new message
    conversation_embeddings = [
        generate_embedding(msg.text) for msg in conversation.lines
    ]
    message_embedding = generate_embedding(message.text)

    # Calculate semantic similarity scores
    similarity_scores = [
        cosine_similarity(conv_emb, message_embedding)
        for conv_emb in conversation_embeddings
    ]

    return (
        max(similarity_scores)
        if max(similarity_scores) >= similarity_threshold
        else 0.0
    )


# Combined Classifier Function
def rule_based_classifier(conversation: Conversation, message: Message) -> bool:
    # Define weights for each rule
    weights = {
        "time_window": 0.4,
        "keyword_matching": 0.3,
        "user_interaction": 0.2,
        "semantic_similarity": 0.1,
    }

    # Evaluate each rule and compute the weighted score
    time_window_score = (
        is_within_time_window(conversation, message) * weights["time_window"]
    )
    keyword_matching_score = (
        has_matching_keywords(conversation, message) * weights["keyword_matching"]
    )
    user_interaction_score = (
        is_reply_to_conversation(conversation, message) * weights["user_interaction"]
    )
    semantic_similarity_score_value = (
        semantic_similarity_score(conversation, message)
        * weights["semantic_similarity"]
    )

    # Compute final score
    final_score = (
        time_window_score
        + keyword_matching_score
        + user_interaction_score
        + semantic_similarity_score_value
    )

    # Define a threshold for the final score
    score_threshold = 0.5

    return final_score >= score_threshold

