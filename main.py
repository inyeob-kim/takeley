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
TWITTER_USER = "Investingcom"
# TWITTER_USER = "BRICSinfo"
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

    🚨 긴급 속보 🚨

    (그 다음 두 줄 개행 후, 다시 작성된 내용)

    🔹 뉴스는 있는 그대로 전해주세요.
    🔹 뉴스 내용에 맞는 긴장감과 어조를 사용해주세요.
    🔹 핵심 정보는 반드시 유지해주세요.
    🔹 트윗의 마지막에는 투자자들이 취해야 할 스탠스를 뉴스를 바탕으로 분석적으로 제시해주세요. 투자와 관련이 없는 뉴스이면 제시안해도 됩니다. 
    🔹 해시태그는 영어로 유지하고, 필요하면 하나 정도만 포함하세요. 이모지는 뉴스 상황에 맞게 써주세요!
    🔹 최종 결과는 한국어로 작성되어야 하며, 해시태그만 영어로 남겨야 합니다.

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

def post_to_twitter(text):
    try:
        client_twitter.create_tweet(text=text)
        print("🐦 Posted to Twitter!")
    except Exception as e:
        print("❌ Failed to post tweet:", e)

# Main loop
def main_loop():
    print("\n🚀 [START] Twitter Translator + Poster")

    posted_tweets = load_json(POSTED_TWEETS_FILE)
    empty_cycle_count = 0

    while True:
        tweets = fetch_latest_tweets(TWITTER_USER, TWEET_LIMIT)

        if not tweets:
            print("⚠️ No new tweets. Skipping...")
            empty_cycle_count += 1
        else:
            empty_cycle_count = 0
            new_posts = []

            for tweet in tqdm(tweets, desc="🧠 Processing Tweets", unit="tweet"):
                if tweet in posted_tweets:
                    print("⏩ Skipping duplicate tweet") 
                    continue

                print("📥 Original Tweet:", tweet)

                # Translate (if needed)
                # translated = translate_to_korean(tweet)
                # post_to_twitter(translated)
 
                # Rewrite as breaking news
                breaking_news_tweet = rewrite_as_breaking_news(tweet)
                print("📝 Breaking News Tweet:", breaking_news_tweet)
                post_to_twitter(breaking_news_tweet)

                new_posts.append(tweet)
                post_delay = random.randint(120, 240)
                wait_with_progress(post_delay)

            posted_tweets.update(new_posts)
            save_json(list(posted_tweets), POSTED_TWEETS_FILE)

        delay = 30
        print(f"✅ Cycle complete. Waiting {delay} seconds before next check...\n")
        wait_with_progress(delay)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 Program terminated by user.")
