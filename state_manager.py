import json
import os
from typing import Any, Dict, List, Optional


def save_json(data: Any, filename: str) -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STATE] save_failed file={filename} error={e}")


def load_json(filename: str, default: Any) -> Any:
    if not os.path.exists(filename):
        return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[STATE] load_failed file={filename} error={e}")
        return default


def get_last_seen_file(username: str) -> str:
    return f"{username}_last_seen_id.txt"


def save_last_seen_id(username: str, tweet_id: int) -> None:
    filename = get_last_seen_file(username)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(str(tweet_id))
    except Exception as e:
        print(f"[STATE] save_last_seen_failed user={username} error={e}")


def load_last_seen_id(username: str) -> Optional[str]:
    filename = get_last_seen_file(username)
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            value = f.read().strip()
            return value or None
    except Exception as e:
        print(f"[STATE] load_last_seen_failed user={username} error={e}")
        return None


def build_posted_id_set(posted_tweets: List[Dict[str, Any]]) -> set:
    return {str(item.get("tweet_id")) for item in posted_tweets}
