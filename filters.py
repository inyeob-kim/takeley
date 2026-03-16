from typing import Set


def is_duplicate(tweet_id: int, posted_id_set: Set[str]) -> bool:
    return str(tweet_id) in posted_id_set


def is_empty_tweet(tweet_text: str) -> bool:
    return not tweet_text or not tweet_text.strip()
