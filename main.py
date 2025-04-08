import tweepy
import openai
from kakao import send_kakao_messages, get_token_file_path, request_kakao_token
import time
import json
import os
from config import set_environment

# Environment Setup
set_environment()

openai.api_key = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
client_twitter = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

CACHE_FILE = "tweets.json"
TWITTER_USER = "DeItaone"
TWEET_LIMIT = 5
TOKENS_DIR = "tokens"
KAKAO_USER_LIST = [
    {
        "name": "me",
        "authorize_code": "Le85xwecYCFk4exT_9q_N4KlYK4_gB2raeacfr3X2-8FOz417BLSzAAAAAQKFxZiAAABlhRSc_ai-KZYUq23DA"
    },
    {
        "name": "ldk",
        "authorize_code": "vO8fvUcAOhqSVcxqz5bqV8EoGeiPpeNYqjqFNJtL9uNL4Tto_-PmrwAAAAQKDRSjAAABlhRSY0nkNSpXBP-m7Q"
    }
]

def translate_to_korean(text, retry=3):
    prompt = f"""
    Please translate the following tweet into Korean. Keep the translation natural and fluent:

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

def fetch_and_cache_tweets_from_user(username, limit, filename):
    try:
        print(f"🔍 Fetching tweets from @{username} (limit: {limit})...")
        user = client_twitter.get_user(username=username)
        user_id = user.data.id

        response = client_twitter.get_users_tweets(id=user_id, max_results=limit)
        tweets = [tweet.text for tweet in response.data] if response.data else []

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tweets, f, ensure_ascii=False, indent=2)

        print("✅ Tweets fetched and cached successfully")
        return tweets

    except Exception as e:
        print(f"❌ Twitter fetch failed: {e}")
        if os.path.exists(filename):
            return load_cached_tweets(filename)
        return []

def load_cached_tweets(filename=CACHE_FILE):
    print("💾 Loading tweets from cache...")
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def main_loop():

    # Me
    for KAKAO_USER in KAKAO_USER_LIST:
        token_path = get_token_file_path(TOKENS_DIR, KAKAO_USER)
        if not os.path.exists(token_path):
            print(f"🔐 No token for {KAKAO_USER}. Requesting token now...")
            request_kakao_token(token_path, KAKAO_USER.get("authorize_code"))

    while True:
        print("\n🚀 [START] Twitter-Kakao Automation Loop")
        tweets = fetch_and_cache_tweets_from_user(TWITTER_USER, TWEET_LIMIT, CACHE_FILE)

        for tweet in tweets:
            translated = translate_to_korean(tweet)
            print(f"🈶 Translated Tweet:\n{translated}")
            send_kakao_messages(TOKENS_DIR, translated) 

        print("⏳ Waiting 15 minutes before next fetch...")
        time.sleep(15 * 60)  # 15분 대기

if __name__ == "__main__":
    main_loop()
