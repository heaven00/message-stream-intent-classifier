import re


def _remove_urls(text: str) -> str:
    """Remove URLs from a text string."""
    url_pattern = r"http\S+|www\.\S+"
    return re.sub(url_pattern, "link", text)


def _remove_user_mentions(text: str) -> str:
    """Remove user mentions (e.g., @username)."""
    user_mention_pattern = r"[@]\w+"
    return re.sub(user_mention_pattern, "user", text)


def _remove_channel_mentions(text: str) -> str:
    """Remove channel mentions (e.g., #channel')."""
    channel_pattern = r"[#]\w+"
    return re.sub(channel_pattern, "group", text)



def _remove_special_chars(text: str) -> str:
    """Remove special characters except basic punctuation."""
    return re.sub(r"[^\w\s.,!?]", "", text)


def clean_text(text: str) -> str:
    """Apply cleaning functions in sequence."""
    text = _remove_urls(text.lower().strip())
    text = _remove_channel_mentions(text)
    text = _remove_user_mentions(text)
    text = _remove_special_chars(text)
    return text
