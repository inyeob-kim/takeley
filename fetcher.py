import time
from typing import Dict, List, Optional, Tuple

import tweepy


AUTH_ERROR = "AUTH_ERROR"
FORBIDDEN = "FORBIDDEN"
RATE_LIMIT = "RATE_LIMIT"
NETWORK_ERROR = "NETWORK_ERROR"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


def classify_error(error: Exception) -> str:
    text = str(error).lower()
    if isinstance(error, tweepy.TooManyRequests):
        return RATE_LIMIT
    if isinstance(error, tweepy.Forbidden):
        return FORBIDDEN
    if isinstance(error, tweepy.Unauthorized):
        return AUTH_ERROR
    if isinstance(error, (tweepy.BadRequest, tweepy.NotFound)):
        return AUTH_ERROR
    if "timeout" in text or "connection" in text or "dns" in text:
        return NETWORK_ERROR
    return UNKNOWN_ERROR


def validate_startup_auth(client: tweepy.Client, username: str = "muskonomy") -> Tuple[bool, str, Optional[Exception]]:
    try:
        client.get_user(username=username)
        print(f"[AUTH] startup_check=ok user={username}")
        return True, "", None
    except Exception as e:
        category = classify_error(e)
        print(f"[AUTH] startup_check=failed category={category} user={username} error={e}")
        return False, category, e


def fetch_user_id(client: tweepy.Client, username: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        user = client.get_user(username=username)
        if not user or not user.data:
            return None, UNKNOWN_ERROR
        return int(user.data.id), None
    except Exception as e:
        return None, classify_error(e)


def fetch_latest_tweets(
    client: tweepy.Client,
    user_id: int,
    limit: int,
    since_id: Optional[str] = None,
) -> Tuple[Optional[List[Tuple[int, str]]], Optional[str]]:
    try:
        params = {"id": user_id, "max_results": limit}
        if since_id:
            params["since_id"] = since_id
        response = client.get_users_tweets(**params)
        tweets_data = response.data or []
        tweets = [(int(tweet.id), tweet.text) for tweet in tweets_data]
        return tweets, None
    except Exception as e:
        return None, classify_error(e)


def rate_limit_wait_seconds(error: Exception) -> int:
    if not isinstance(error, tweepy.TooManyRequests):
        return 60
    reset = int(getattr(error.response, "headers", {}).get("x-rate-limit-reset", time.time() + 60))
    return max(0, reset - int(time.time()))
