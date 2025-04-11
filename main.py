import tweepy
import openai
import time
import os
import json
from config import set_environment
from tqdm import tqdm
import random
import asyncio
import functools
from collections import deque

# 🔧 Load environment variables
set_environment()

# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# 사용자 큐 설정
user_queue = deque(["TrumpDailyPosts", "DeItaone", "Investingcom", "BRICSinfo"])
TWEET_LIMIT = 5

# Twitter Clients
client_twitter_read = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

client_twitter = tweepy.Client(
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"), 
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)

CACHE_FILE = "tweets.json"
POSTED_TWEETS_FILE = "posted_tweets.json"

# File helpers
def save_json(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Failed to save {filename}: {e}")

def load_json(filename):
    if not os.path.exists(filename):
        return set()
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception as e:
        print(f"⚠️ Failed to load {filename}: {e}")
        return set()

def get_last_seen_file(username):
    return f"{username}_last_seen_id.txt"

def save_last_seen_id(username, tweet_id):
    filename = get_last_seen_file(username)
    try:
        with open(filename, "w") as f:
            f.write(str(tweet_id))
    except Exception as e:
        print(f"❌ Failed to save last seen ID for {username}: {e}")

def load_last_seen_id(username):
    filename = get_last_seen_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return f.read().strip()
        except Exception as e:
            print(f"⚠️ Failed to read last seen ID for {username}: {e}")
    return None

def wait_with_progress(seconds):
    for _ in tqdm(range(seconds), desc=f"⏳ Waiting {seconds}s (rate limit)", unit="s"):
        time.sleep(1)

# GPT Functions (동기 → executor)
def rewrite_as_breaking_news(text, retry=3):
    prompt = f"""
        당신은 '주식이 미쳤다 뉴스'라는 가상의 글로벌 금융 속보 매체의 기자입니다.

        당신의 임무는 트위터 속보를 **한글로 번역해**, 아래 형식의 **시선을 끄는 실시간 속보 뉴스 템플릿**으로 작성하는 것입니다.

        반드시 아래 출력 규칙을 지켜주세요:

        🚨 실시간 뉴스 | 글로벌 이슈 속보
        (두 줄 개행 후)
        첫 줄: 핵심 인물 또는 기관 + 행동/사건 요약
        둘째 줄: 시장에 미칠 영향 요약
        셋째 줄: 향후 일정이나 예고

        주의:
        - 전체는 반드시 **3~4줄 이내**, 간결하고 강렬하게
        - 핵심 정보(기관명, 숫자, 국가 등)는 원문 그대로 사용 가능
        - 해시태그는 절대 사용하지 말 것
        - 분석, 감성, 의견은 절대 넣지 말고 **사실(Fact)만** 전달
        - 만약 특별한 의미가 있는 트윗이라고 판단이 되지 않으면, 그냥 해석해서 있는 그대로 전달
        - 만약 트윗이 URL 링크뿐이라면 그냥 해석할 필요 없고 empty string 리턴.

        트윗 원문:
        \"{text}\"
    """
    for attempt in range(retry): 
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Rewriting failed (attempt {attempt+1}/{retry}): {e}")
            time.sleep(2)
    return f"번역 실패. 원문 그대로 전달:\n\n{text}"

# 트윗 가져오기
def fetch_latest_tweets(username, limit):
    try:
        user = client_twitter_read.get_user(username=username)
        user_id = user.data.id

        since_id = load_last_seen_id(username)
        params = {"id": user_id, "max_results": limit}
        if since_id:
            params["since_id"] = since_id

        response = client_twitter_read.get_users_tweets(**params)
        tweets_data = response.data or []
        print(f"📊 @{username}: {len(tweets_data)} tweets fetched.")
        tweets = [(tweet.id, tweet.text) for tweet in tweets_data]

        if tweets_data:
            latest_id = max(tweet.id for tweet in tweets_data)
            save_last_seen_id(username, latest_id)

        return tweets
    except tweepy.TooManyRequests as e:
        reset = int(e.response.headers.get("x-rate-limit-reset", time.time() + 60))
        wait_seconds = max(0, reset - int(time.time()))
        print(f"🚫 Rate limit hit for @{username}. Waiting {wait_seconds} seconds...")
        wait_with_progress(wait_seconds)
        return fetch_latest_tweets(username, limit)
    except Exception as e:
        print(f"❌ Twitter fetch failed for {username}: {e}")
        return []

# 트윗 작성
def post_to_twitter(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            client_twitter.create_tweet(text=text)
            print("🐦 Posted to Twitter!")
            return True
        except Exception as e:
            print(f"❌ Tweet post failed: {e}")
            time.sleep(5)
    return False

# 사용자별 트윗 처리
def process_user(username, posted_tweets):
    tweets = fetch_latest_tweets(username, TWEET_LIMIT)
    new_posts = []
    for tweet_id, tweet_text in tweets:
        if str(tweet_id) in posted_tweets:
            continue

        if not tweet_text.strip():
            print(f"⚠️ Skipping @{username}'s tweet ({tweet_id}) due to empty text.")
            continue

        print(f"🧠 @{username}: {tweet_text}")
        breaking_news = rewrite_as_breaking_news(tweet_text)
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        final_text = f"{breaking_news}\n\n🔗 {tweet_url}"

        success = post_to_twitter(final_text)
        if success:
            new_posts.append(str(tweet_id))

    posted_tweets.update(new_posts)
    save_json(list(posted_tweets), POSTED_TWEETS_FILE)

# 메인 루프
def main_loop():
    print("\n🚀 [START] Serial Twitter Translator + Poster (1 user per minute)")
    posted_tweets = load_json(POSTED_TWEETS_FILE)

    while True:
        username = user_queue.popleft()
        process_user(username, posted_tweets)
        user_queue.append(username)
        print(f"✅ Done with @{username}. Waiting 60s before next user...\n")
        wait_with_progress(60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 Program terminated by user.")
