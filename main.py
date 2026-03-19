import os
import sys
import time
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import openai
import tweepy
from tqdm import tqdm

from ai_processor import analyze_tweet_for_posting
from config import set_environment
from content_formatter import (
    OPENING_PREFIXES,
    assemble_final_post_text,
    is_repetitive_line,
    rebalance_format_type,
)
from fetcher import RATE_LIMIT, fetch_latest_tweets, fetch_user_id, validate_startup_auth
from filters import is_duplicate, is_empty_tweet
from poster import post_with_optional_image
from scheduler import AccountScheduler
from state_manager import (
    build_posted_id_set,
    load_json,
    load_last_seen_id,
    save_json,
    save_last_seen_id,
)
from summary_report import post_interim_report


# Load env once (config.py now guards against duplicate calls).
set_environment()

openai.api_key = os.getenv("OPENAI_API_KEY") 
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

client_twitter_read = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
client_twitter = tweepy.Client( 
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"), 
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)

auth_v1 = tweepy.OAuth1UserHandler(
    os.getenv("TWITTER_API_KEY"),
    os.getenv("TWITTER_API_SECRET"),
    os.getenv("TWITTER_ACCESS_TOKEN"),
    os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)
api_v1 = tweepy.API(auth_v1)
 
POSTED_TWEETS_FILE = "posted_tweets.json"
USER_ID_FILE = "user_ids.json"
TWEET_COUNT_STATE_FILE = "tweet_count_state.json"
NEW_TWEET_RANGE = 20
FETCH_SCAN_INTERVAL_SECONDS = 30
FETCH_LIMIT_PER_USER = 5

TIER1_ACCOUNTS = ["Investingcom", "FirstSquawk", "DeItaone"]
TIER2_ACCOUNTS = ["unusual_whales", "SawyerMerritt", "StockMKTNewz"]


def debug_env() -> None:
    """
    Print presence and short prefix of required env vars.
    Never prints full secret values.
    """
    keys = [
        "OPENAI_API_KEY",
        "TWITTER_BEARER_TOKEN",
        "TWITTER_API_KEY",
        "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN",
        "TWITTER_ACCESS_TOKEN_SECRET",
    ]
    print("[ENV] Debug check start")
    for key in keys:
        value = os.getenv(key, "")
        if value:
            prefix = value[:4]
            print(f"[ENV] {key}: present (prefix={prefix}...)")
        else:
            print(f"[ENV] {key}: missing")


def wait_with_progress(seconds: int) -> None:
    for _ in tqdm(range(seconds), desc=f"Waiting {seconds}s", unit="s"):
        time.sleep(1)


def is_within_active_hours(start_time: str = "06:00", end_time: str = "23:00", test_mode: bool = False) -> bool:
    if test_mode:
        return True

    now_kst = datetime.now(ZoneInfo("Asia/Seoul")).time()
    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(end_time, "%H:%M").time()

    if start_time_obj < end_time_obj:
        return start_time_obj <= now_kst < end_time_obj
        return now_kst >= start_time_obj or now_kst < end_time_obj
    

def _extract_opening_prefix(content: str) -> str:
    text = (content or "").strip()
    for prefix in OPENING_PREFIXES:
        if text.startswith(prefix):
            return prefix
    return ""


def _infer_format_type_from_content(content: str) -> str:
    text = (content or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    source_index = next(
        (
            idx
            for idx, line in enumerate(lines)
            if line.startswith("@") or line.startswith("출처 계정:") or line.startswith("출처:")
        ),
        -1,
    )
    main_lines = lines[:source_index] if source_index > 0 else lines

    has_implication = any(line.startswith("👉") or line.startswith("→") for line in main_lines)
    if not has_implication:
        return "news_only"

    implication_index = next(
        (
            idx
            for idx, line in enumerate(main_lines)
            if line.startswith("👉") or line.startswith("→")
        ),
        -1,
    )
    follow_lines = main_lines[implication_index + 1 :] if implication_index != -1 else []
    if not follow_lines:
        return "news_implication"

    engagement_line = follow_lines[0]
    if "리포스트" in engagement_line or "공유" in engagement_line:
        return "news_implication_repost"
    return "news_implication_question"


def _build_text_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _recent_values(posted_tweets: List[Dict], key: str, limit: int = 10) -> List[str]:
    values = []
    for item in posted_tweets[-limit:]:
        value = str(item.get(key, "")).strip()
        if value:
            values.append(value)
    return values


def _recent_format_types(posted_tweets: List[Dict], limit: int = 60) -> List[str]:
    result: List[str] = []
    for item in posted_tweets[-limit:]:
        fmt = str(item.get("format_type", "")).strip().lower()
        if not fmt:
            fmt = _infer_format_type_from_content(str(item.get("content", "")))
        result.append(fmt)
    return result


def process_user(
    username: str,
    posted_tweets: List[Dict],
    posted_id_set: set,
    user_ids: Dict[str, int],
) -> Tuple[int, str]:
    posted_count = 0

    user_id = user_ids.get(username)
    if not user_id:
        fetched_user_id, user_error = fetch_user_id(client_twitter_read, username)
        if user_error:
            print(f"[FETCH] user={username} stage=user_lookup status=failed category={user_error}")
            return 0, user_error
        user_id = fetched_user_id
        user_ids[username] = int(user_id)
        save_json(user_ids, USER_ID_FILE)

    since_id = load_last_seen_id(username)
    tweets, fetch_error = fetch_latest_tweets(
        client_twitter_read,
        int(user_id),
        FETCH_LIMIT_PER_USER,
        since_id=since_id,
    )
    if fetch_error:
        print(f"[FETCH] user={username} status=failed category={fetch_error}")
        return 0, fetch_error

    tweets = tweets or []
    print(f"[FETCH] user={username} new_tweets={len(tweets)} since_id={since_id}")
    if not tweets:
        return 0, "OK"

    # Process from oldest -> newest.
    # since_id policy:
    # - advance only when a tweet is fully "processed" (filtered or posted)
    # - do NOT advance when temporary failures occur (AI/posting failures),
    #   so those tweets can be retried later and are not lost.
    tweets.sort(key=lambda item: item[0])
    recent_posts = _recent_values(posted_tweets, "content", limit=10)
    recent_implications = _recent_values(posted_tweets, "implication", limit=12)
    recent_engagements = _recent_values(posted_tweets, "engagement", limit=12)
    recent_prefixes = [
        value
        for value in (_extract_opening_prefix(item.get("content", "")) for item in posted_tweets[-20:])
        if value
    ]
    recent_format_types = _recent_format_types(posted_tweets, limit=60)

    for tweet_id, tweet_text in tweets:
        processed = False

        if is_duplicate(tweet_id, posted_id_set):
            print(f"[FILTER] tweet_id={tweet_id} reason=duplicate")
            processed = True
        elif is_empty_tweet(tweet_text):
            print(f"[FILTER] tweet_id={tweet_id} reason=empty")
            processed = True
        else:
            ai_result = analyze_tweet_for_posting(
                tweet_text,
                username,
                recent_posts,
                recent_implications=recent_implications,
                recent_engagements=recent_engagements,
                retry=2,
            )
            if not ai_result.get("ok"):
                print(f"[AI] classification=error tweet_id={tweet_id} error={ai_result.get('error', 'unknown')}")
                processed = False
            elif not ai_result.get("is_relevant", False):
                print(f"[FILTER] tweet_id={tweet_id} reason={ai_result.get('skip_reason', 'irrelevant')}")
                print(f"[AI] skip_reason={ai_result.get('skip_reason', 'irrelevant')}")
                processed = True
            elif ai_result.get("is_similar", False):
                print(f"[FILTER] tweet_id={tweet_id} reason=similarity")
                processed = True
            else:
                summary = ai_result.get("summary", "").strip()
                implication = ai_result.get("implication", "").strip()
                format_type = ai_result.get("format_type", "news_implication")
                news_type = ai_result.get("news_type", "neutral")
                engagement = ai_result.get("engagement", "").strip()
                hashtags = ai_result.get("hashtags", "").strip()
                if not summary:
                    print(f"[AI] classification=error tweet_id={tweet_id} error=empty_summary")
                    processed = False
                else:
                    if is_repetitive_line(implication, recent_implications[-8:], max_recent_reuse=1):
                        print("[AI] implication_dropped reason=repetition")
                        implication = ""
                    if is_repetitive_line(engagement, recent_engagements[-8:], max_recent_reuse=1):
                        print("[AI] engagement_dropped reason=repetition")
                        engagement = ""

                    format_type = rebalance_format_type(
                        suggested_format_type=format_type,
                        news_type=news_type,
                        has_implication=bool(implication),
                        has_engagement=bool(engagement),
                        recent_format_types=recent_format_types,
                    )

                    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
                    final_text, normalized_format_type = assemble_final_post_text(
                        format_type=format_type,
                        summary=summary,
                        implication=implication,
                        engagement=engagement,
                        hashtags=hashtags,
                        tweet_url=tweet_url,
                        recent_prefixes=recent_prefixes,
                    )

                    implication_added = "yes" if ("\n\n👉" in final_text or "\n\n→" in final_text) else "no"
                    engagement_added = "yes" if bool(engagement) and normalized_format_type in {
                        "news_implication_question",
                        "news_implication_repost",
                    } else "no"
                    print(f"[AI] classification=relevant tweet_id={tweet_id}")
                    print(f"[AI] news_type={news_type}")
                    print(f"[AI] format_type={normalized_format_type}")
                    print(f"[AI] implication_added={implication_added}")
                    print(f"[AI] engagement_added={engagement_added}")
                    print(f"[AI] hashtags={hashtags or 'none'}")
                    print(
                        f"[POST_DIAG] stage=pre_post "
                        f"tweet_id={tweet_id} "
                        f"source_user={username} "
                        f"text_len={len(final_text)} "
                        f"line_count={len([line for line in final_text.splitlines() if line.strip()])} "
                        f"mention_count={len(re.findall(r'(^|\\s)@[A-Za-z0-9_]{1,15}', final_text))} "
                        f"url_count={len(re.findall(r'https?://\\S+', final_text))} "
                        f"fingerprint={_build_text_fingerprint(final_text)}"
                    )
                    success, mode = post_with_optional_image(
                        client_twitter,
                        api_v1,
                        final_text,
                        tweet_text,
                        tweet_id,
                    )
                    if success:
                        stored_implication = implication if normalized_format_type != "news_only" else ""
                        stored_engagement = (
                            engagement
                            if normalized_format_type in {"news_implication_question", "news_implication_repost"}
                            else ""
                        )
                        posted_tweets.append(
                            {
                                "tweet_id": tweet_id,
                                "content": summary,
                                "implication": stored_implication,
                                "engagement": stored_engagement,
                                "hashtags": hashtags,
                                "format_type": normalized_format_type,
                                "news_type": news_type,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
                        posted_id_set.add(str(tweet_id))
                        recent_posts.append(summary)
                        if stored_implication:
                            recent_implications.append(stored_implication)
                        if stored_engagement:
                            recent_engagements.append(stored_engagement)
                        recent_format_types.append(normalized_format_type)
                        recent_prefix = _extract_opening_prefix(final_text)
                        if recent_prefix:
                            recent_prefixes.append(recent_prefix)
                        posted_count += 1
                        print(f"[POST] success tweet_id={tweet_id} mode={mode}")
                        print(f"[POST] mode={mode}")
                        wait_with_progress(10)
                        processed = True
                    else:
                        print(f"[POST] failed tweet_id={tweet_id} mode={mode}")
                        processed = False

        if processed:
            save_last_seen_id(username, tweet_id)
        else:
            print(f"[STATE] since_id_not_advanced user={username} tweet_id={tweet_id} reason=temporary_failure")
            break

    if posted_count > 0:
        save_json(posted_tweets, POSTED_TWEETS_FILE)
    return posted_count, "OK"


def main_loop(test_mode: bool = False) -> None:
    print("\n[START] Priority Twitter Translator + Poster")
    posted_tweets = load_json(POSTED_TWEETS_FILE, [])
    if not isinstance(posted_tweets, list):
        posted_tweets = []
    posted_id_set = build_posted_id_set(posted_tweets)

    user_ids = load_json(USER_ID_FILE, {})
    if not isinstance(user_ids, dict):
        user_ids = {}

    tweet_count_state = load_json(TWEET_COUNT_STATE_FILE, {})
    if not isinstance(tweet_count_state, dict):
        tweet_count_state = {}
    last_interim_count = int(tweet_count_state.get("last_interim_count", 0))
    recent_tweets: List[Dict] = []

    total_num_posts_today = 0
    scheduler = AccountScheduler(TIER1_ACCOUNTS, TIER2_ACCOUNTS)

    if test_mode:
        print("[MODE] test_mode=true no_special_script")
        return

    while True: 
        if not is_within_active_hours(start_time="06:00", end_time="23:00", test_mode=False):
            print("[SCHED] outside_active_hours=true sleep=30")
            wait_with_progress(FETCH_SCAN_INTERVAL_SECONDS)
            continue

        due_accounts = scheduler.due_accounts()
        if not due_accounts:
            print("[SCHED] due_accounts=0 sleep=30")
            wait_with_progress(FETCH_SCAN_INTERVAL_SECONDS)
            continue

        print(f"[SCHED] due_accounts={len(due_accounts)} users={','.join(due_accounts)}")
        for username in due_accounts:
            before_count = len(posted_tweets) 
            posted_count, status = process_user(username, posted_tweets, posted_id_set, user_ids)
            total_num_posts_today += posted_count

            new_tweets_slice = posted_tweets[before_count:]
            recent_tweets.extend(new_tweets_slice)

            current_tweet_count = len(posted_tweets)
            new_tweets = current_tweet_count - last_interim_count 
            print(
                f"[STATE] total_posts={total_num_posts_today} "
                f"stored_posts={current_tweet_count} new_since_interim={new_tweets}"
            )

            if new_tweets >= NEW_TWEET_RANGE:
                print(f"[REPORT] interim_trigger=true size={NEW_TWEET_RANGE}")
                tweets_to_report = recent_tweets[-NEW_TWEET_RANGE:]
                post_interim_report(new_tweets, tweets_to_report)
                last_interim_count = current_tweet_count
                tweet_count_state["last_interim_count"] = last_interim_count
                save_json(tweet_count_state, TWEET_COUNT_STATE_FILE)
                recent_tweets.clear()
 
            if status == RATE_LIMIT:
                scheduler.mark_fetched(username, defer_minutes=15)
                print(f"[RATE_LIMIT] user={username} pause_minutes=15")
            else:
                scheduler.mark_fetched(username)

        wait_with_progress(FETCH_SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    debug_env()
    ok, category, _ = validate_startup_auth(client_twitter_read, username="muskonomy")
    if not ok:
        print(f"[AUTH] startup_validation_failed category={category} action=exit")
        sys.exit(1)
    main_loop(test_mode=False)
