import tweepy
import openai
import time
import os
import json
from config import set_environment
from tqdm import tqdm
import random

# 🔧 Load environment variables
set_environment()

# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# 유저 큐 설정
user_queue = ["DeItaone", "Investingcom", "BRICSinfo"]  # 원하는 유저를 이 리스트에 추가하세요

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
        print(f"💾 Data saved to {filename}")
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
    for _ in tqdm(range(seconds), desc=f"⏳ Waiting {seconds}s", unit="sec", ncols=80):
        time.sleep(1)

# GPT Functions
def translate_to_korean(text, retry=3):
    prompt = f"""
    다음 트윗을 한국어로 번역해주세요. 자연스럽고 유창한 문장으로 번역하되, 마치 속보처럼 긴박하고 주목을 끌 수 있는 어조로 전달해주세요:

    "{text}"
    """
    for attempt in range(retry):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ Translation failed (attempt {attempt+1}/{retry}): {e}")
            time.sleep(2)
    return text

def rewrite_as_breaking_news(text, retry=3):
    prompt = f"""
    다음 트윗을 "WhyMyStocksHateMeSoMuch 뉴스"라는 가상의 금융 뉴스 매체의 긴급 속보처럼 다시 작성해주세요.

    출력은 반드시 아래 형식으로 시작해야 합니다:

    🚨 실시간 뉴스 🚨

    (그 다음 두 줄 개행 후, 다시 작성된 내용)

    🔹 뉴스 내용에 맞는 짧고 간결하고 긴장감과 어조를 사용해주세요.
    🔹 핵심 정보는 반드시 유지해주세요.

    트윗 원문:
    "{text}"
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
    return f"WhyMyStocksHateMeSoMuch 뉴스:\n\n{text}"

# Twitter fetch and post
def fetch_latest_tweets(username, limit):
    try:
        print(f"🔍 Fetching tweets from @{username} (limit: {limit})...")
        user = client_twitter_read.get_user(username=username)
        user_id = user.data.id

        since_id = load_last_seen_id(username)
        params = {"id": user_id, "max_results": limit}
        if since_id:
            params["since_id"] = since_id

        response = client_twitter_read.get_users_tweets(**params)
        tweets_data = response.data or []
        tweets = [tweet.text for tweet in tweets_data]

        if tweets_data:
            latest_id = tweets_data[0].id
            save_last_seen_id(username, latest_id)

        print(f"✅ {len(tweets)} new tweets fetched")
        save_json(tweets, CACHE_FILE)
        return tweets

    except tweepy.TooManyRequests as e:
        reset_time = int(e.response.headers.get("x-rate-limit-reset", time.time() + 60))
        wait_seconds = max(0, reset_time - int(time.time()))
        print(f"🚫 Rate limit hit. Waiting {wait_seconds} seconds before retrying...")
        wait_with_progress(wait_seconds)
        return fetch_latest_tweets(username, limit)

    except Exception as e:
        print(f"❌ Twitter fetch failed: {e}")
        return []

def post_to_twitter(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            client_twitter.create_tweet(text=text)
            print("🐦 Posted to Twitter!")
            return True
        except tweepy.TooManyRequests as e:
            # reset_time = int(e.response.headers.get("x-rate-limit-reset", time.time() + 60))
            # wait_seconds = max(60, reset_time - int(time.time()))
            wait_seconds = 30
            print(f"🚫 Rate limit hit. Waiting {wait_seconds} seconds before retrying...")
            wait_with_progress(wait_seconds)
        except Exception as e:
            print(f"❌ Failed to post tweet (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(10 + attempt * 5)  # Exponential-ish backoff
    print("⚠️ Failed to post after retries.")
    return False

# Main Loop
def main_loop():
    print("\n🚀 [START] Twitter Translator + Poster")

    posted_tweets = load_json(POSTED_TWEETS_FILE)
    empty_cycle_count = 0

    while True:
        if not user_queue:
            print("⚠️ 유저 큐가 비어 있습니다.")
            break

        username = user_queue.pop(0)  # 맨 앞 사용자 꺼내기
        print(f"\n🔁 Checking tweets for: @{username}")
        tweets = fetch_latest_tweets(username, TWEET_LIMIT)

        if not tweets:
            print(f"⚠️ No new tweets for @{username}. Re-adding to end of queue.")
            empty_cycle_count += 1
        else:
            empty_cycle_count = 0
            new_posts = []

            for tweet in tqdm(tweets, desc=f"🧠 Processing Tweets from @{username}", unit="tweet"):
                if tweet in posted_tweets:
                    print("⏩ Skipping duplicate tweet") 
                    continue

                print("📥 Original Tweet:", tweet)

                breaking_news_tweet = rewrite_as_breaking_news(tweet)
                print("📝 Breaking News Tweet:", breaking_news_tweet)

                # send_kakao_message(breaking_news_tweet)  # 카카오 연동 시 사용

                success = post_to_twitter(breaking_news_tweet)

                if success:
                    new_posts.append(tweet)
                    post_delay = random.randint(30, 60)
                    wait_with_progress(post_delay)
                else:
                    print("⛔ Tweet skipped after failed attempts.")

            posted_tweets.update(new_posts)
            save_json(list(posted_tweets), POSTED_TWEETS_FILE)

        # 무조건 사용자 다시 큐 뒤로 추가
        user_queue.append(username)

        delay = 30
        print(f"✅ Cycle complete. Waiting {delay} seconds before next check...\n")
        wait_with_progress(delay)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 Program terminated by user.")
