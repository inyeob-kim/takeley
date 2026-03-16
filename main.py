import os
import smtplib
import sys
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import openai
import tweepy
from tqdm import tqdm

from ai_processor import analyze_tweet_for_posting
from config import set_environment
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
from summary_report import post_interim_report, post_summary_report


# Load env once (config.py now guards against duplicate calls).
set_environment()

openai.api_key = os.getenv("OPENAI_API_KEY") 
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

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
X_POST_MAX_LEN = 280

TIER1_ACCOUNTS = ["Investingcom", "BRICSinfo", "DeItaone"]
TIER2_ACCOUNTS = ["muskonomy", "SawyerMerritt", "TheSonOfWalkley"]


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
        "EMAIL_ADDRESS",
        "EMAIL_PASSWORD",
        "EMAIL_RECEIVER",
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
    

def parse_time_str(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"[STATE] time_parse_failed value={value} error={e}")
        return None


def compose_post_text(
    summary: str,
    question: str,
    username: str,
    tweet_url: str,
    max_len: int = X_POST_MAX_LEN,
) -> str:
    source_block = f"@{username}\n\n출처: {tweet_url}"
    summary = (summary or "").strip()
    question = (question or "").strip()

    if question:
        body = f"{summary}\n\n{question}"
    else:
        body = summary

    full_text = f"{body}\n\n{source_block}"
    if len(full_text) <= max_len:
        return full_text

    # Keep attribution intact and trim body first.
    allowed_body_len = max_len - len(f"\n\n{source_block}")
    if allowed_body_len <= 0:
        return source_block[:max_len]

    body = body[:allowed_body_len].rstrip()
    if len(body) < len(f"{summary}\n\n{question}" if question else summary) and allowed_body_len >= 1:
        body = body[:-1].rstrip() + "…"

    return f"{body}\n\n{source_block}"


def send_script_email(script_text: str) -> None:
    msg = MIMEMultipart()
    msg["Subject"] = "오늘의 유튜브 요약 스크립트"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECEIVER
    body = f"안녕하세요,\n\n오늘 생성된 유튜브 대본입니다:\n\n{script_text}\n\n감사합니다."
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("[SCRIPT] email_sent=true")
    except Exception as e:
        print(f"[SCRIPT] email_sent=false error={e}")


def generate_youtube_script() -> str | None:
    print("[SCRIPT] generate_start=true")
    try:
        posted_tweets = load_json(POSTED_TWEETS_FILE, [])
        kst = ZoneInfo("Asia/Seoul")
        now_kst = datetime.now(kst)
        today_date = now_kst.date()
        yesterday_date = today_date - timedelta(days=1)

        start_time = datetime.combine(yesterday_date, datetime.min.time(), tzinfo=kst).replace(hour=22)
        end_time = datetime.combine(today_date, datetime.min.time(), tzinfo=kst).replace(hour=6)
        start_time_naive = start_time.replace(tzinfo=None)
        end_time_naive = end_time.replace(tzinfo=None)

        filtered_tweets = []
        for item in posted_tweets:
            tweet_time = parse_time_str(item.get("time", ""))
            if tweet_time is None:
                continue
            if start_time_naive <= tweet_time <= end_time_naive:
                filtered_tweets.append(item)

        print(f"[SCRIPT] source_total={len(posted_tweets)} filtered={len(filtered_tweets)}")
        if not filtered_tweets:
            return None

        contents = "\n".join([f"- {item['content']}" for item in filtered_tweets])
        prompt = f"""
            당신은 ‘주식이 미쳤다 뉴스’ 채널의 콘텐츠 작성자입니다.
            아래는 최근 12시간 동안 수집된 글로벌 금융 뉴스 트윗 모음입니다.
이 중에서 실제로 투자자에게 중요한 뉴스만 선별하여 각 트윗마다 아래 형식으로 작성하세요.

헤드라인: (30~40자 이내, 한 문장)
본문: (속보 문체, 최대 80자 이내, 사실 중심)

규칙:
1) 각 뉴스마다 1개의 헤드라인 + 1개의 본문
2) 사실 기반, 추측/광고/사견 금지
3) 각 뉴스는 줄바꿈으로 구분

뉴스 트윗:
            {contents}
        """
        response = openai.chat.completions.create( 
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        script = response.choices[0].message.content.strip()

        filename = "filtered_tweet_summaries.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(script)
        print(f"[SCRIPT] saved=true file={filename}")
        send_script_email(script)
        return script
    except Exception as e:
        print(f"[SCRIPT] generate_failed error={e}")
        return None


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
    recent_posts = [item.get("content", "") for item in posted_tweets[-10:]]

    for tweet_id, tweet_text in tweets:
        processed = False

        if is_duplicate(tweet_id, posted_id_set):
            print(f"[FILTER] tweet_id={tweet_id} reason=duplicate")
            processed = True
        elif is_empty_tweet(tweet_text):
            print(f"[FILTER] tweet_id={tweet_id} reason=empty")
            processed = True
        else:
            ai_result = analyze_tweet_for_posting(tweet_text, username, recent_posts, retry=2)
            if not ai_result.get("ok"):
                print(f"[AI] classification=error tweet_id={tweet_id} error={ai_result.get('error', 'unknown')}")
                processed = False
            elif not ai_result.get("is_relevant", False):
                print(f"[FILTER] tweet_id={tweet_id} reason={ai_result.get('skip_reason', 'irrelevant')}")
                processed = True
            elif ai_result.get("is_similar", False):
                print(f"[FILTER] tweet_id={tweet_id} reason=similarity")
                processed = True
            else:
                summary = ai_result.get("summary", "").strip()
                news_type = ai_result.get("news_type", "neutral")
                engagement_type = ai_result.get("engagement_type", "none")
                engagement = ai_result.get("engagement", "").strip()
                if not summary:
                    print(f"[AI] classification=error tweet_id={tweet_id} error=empty_summary")
                    processed = False
                else:
                    print(f"[AI] classification=relevant tweet_id={tweet_id}")
                    print(f"[AI] news_type={news_type} engagement_type={engagement_type}")
                    if engagement:
                        print("[AI] engagement added=true")
                    else:
                        print("[AI] engagement skipped")
                    tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
                    if engagement:
                        final_text = compose_post_text(summary, engagement, username, tweet_url)
                    else:
                        final_text = compose_post_text(summary, "", username, tweet_url)
                    success, mode = post_with_optional_image(
                        client_twitter,
                        api_v1,
                        final_text,
                        tweet_text,
                        tweet_id,
                    )
                    if success:
                        posted_tweets.append(
                            {
                                "tweet_id": tweet_id,
                                "content": summary,
                                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
                        posted_id_set.add(str(tweet_id))
                        recent_posts.append(summary)
                        posted_count += 1
                        print(f"[POST] success tweet_id={tweet_id} mode={mode}")
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


def check_and_run_daily_script(is_daily_script_sent: bool) -> bool:
    now_time = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%H:%M")
    if "06:00" <= now_time < "06:20" and not is_daily_script_sent:
        print("[SCRIPT] window_open=true run_once=true")
        generate_youtube_script()
        return True
    if now_time >= "06:20":
        return False
    return is_daily_script_sent


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

    is_daily_script_sent = False
    total_num_posts_today = 0
    scheduler = AccountScheduler(TIER1_ACCOUNTS, TIER2_ACCOUNTS)

    if test_mode:
        generate_youtube_script()
        print("[SCRIPT] test_mode_done=true")
        return

    while True: 
        if not is_within_active_hours(start_time="06:00", end_time="23:00", test_mode=False):
            print("[SCHED] outside_active_hours=true sleep=30")
            is_daily_script_sent = check_and_run_daily_script(is_daily_script_sent)
            wait_with_progress(FETCH_SCAN_INTERVAL_SECONDS)
            continue

        due_accounts = scheduler.due_accounts()
        if not due_accounts:
            print("[SCHED] due_accounts=0 sleep=30")
            is_daily_script_sent = check_and_run_daily_script(is_daily_script_sent)
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

        is_daily_script_sent = check_and_run_daily_script(is_daily_script_sent)
        wait_with_progress(FETCH_SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    debug_env()
    ok, category, _ = validate_startup_auth(client_twitter_read, username="muskonomy")
    if not ok:
        print(f"[AUTH] startup_validation_failed category={category} action=exit")
        sys.exit(1)

    # Keep feature compatibility: summary report entry-point remains imported.
    _ = post_summary_report
    main_loop(test_mode=False)
