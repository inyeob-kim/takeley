import tweepy
import openai
import time
import os
import json
from config import set_environment
from tqdm import tqdm
from collections import deque
from datetime import datetime, timezone, timedelta
import random
import pytz
from summary_report import post_summary_report, post_interim_report

# 🔧 Load environment variables 
set_environment()

# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
 
# 사용자 큐 설정
user_queue = deque(["Investingcom", "KobeissiLetter", "DeItaone", "TrumpDailyPosts"])

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
USER_ID_FILE = "user_ids.json"  # 파일로 저장할 user_id 파일

# File helpers
def save_json(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Failed to save {filename}: {e}")

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load {filename}: {e}")
        return {}

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
    for _ in tqdm(range(seconds), desc=f"⏳ Waiting {seconds}s", unit="s"):
        time.sleep(1)

def rewrite_as_breaking_news(text, username, retry=3):

    prompt = f"""
    당신은 '주식이 미쳤다 뉴스'라는 가상의 글로벌 금융 속보 매체의 기자입니다.

    당신의 임무는 트위터 속보를 **한글로 번역해**, 아래 형식의 **시선을 끄는 실시간 속보 뉴스 템플릿**으로 작성하는 것입니다.

    아래 출력 형식을 반드시 지켜주세요:

    🚨 글로벌 이슈 속보
    \n\n
    핵심 인물 또는 기관 + 행동/사건 요약 
    → 실제 무슨 일이 벌어졌는지 **구체적으로** 설명

    주의 사항: 
    - 전체는 반드시 **6줄 이내**, 간결하고 강력하게
    - "**중요한 발표**", "**중요한 내용**"과 같이 **모호한 표현은 절대 사용하지 마세요**
    - 핵심 정보(기관명, 숫자, 국가 등)는 원문 그대로 사용 가능
    - 분석이나 의견 없이 **객관적인 사실만** 전달할 것
    - 긴 트윗이라도 핵심 정보 위주로 압축할 것
    - 만약 트윗이 URL 링크뿐이라면 ⬇️⬇️⬇️ 리턴
    - **트윗 내용이 특정 상장 기업과 직접적으로 관련 있을 경우**, 해당 기업의 티커를 뉴스 본문 중 적절한 위치에 **$TSLA $NVDA** 형식으로 포함하세요. 관련 없다면 티커는 생략하세요.

    트윗 원문 (작성자: @{username}): 
    \"{text}\" 

    출력 형식: 
    뉴스 본문 내용 (6줄 이내, 간결하고 강력하게)

    티커가 존재할 경우:  
    [본문]   
    \n\n  
    $TSLA $NVDA (티커 여러 개 가능)  
    \n\n  
    #Hashtag1 #Hashtag2 #Hashtag3 (2~3개, 반드시 뉴스와 직접적인 관련이 있어야 함)

    티커가 존재하지 않을 경우:  
    [본문]  
    \n\n  
    #Hashtag1 #Hashtag2 #Hashtag3 (2~3개, 반드시 뉴스와 직접적인 관련이 있어야 함)
    """

    for attempt in range(retry): 
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            ) 
            result = response.choices[0].message.content.strip()

            return result

        except Exception as e:
            print(f"⚠️ Rewriting failed (attempt {attempt+1}/{retry}): {e}")
            time.sleep(2)

    return f"번역 실패. 원문 그대로 전달:\n\n{text}"

# 트윗 가져오기 (user_id를 미리 가져와서 사용)
def fetch_user_id(username):
    try:
        user = client_twitter_read.get_user(username=username)
        user_id = user.data.id
        return user_id
    except tweepy.TooManyRequests as e:
        reset = int(e.response.headers.get("x-rate-limit-reset", time.time() + 60))
        wait_seconds = max(0, reset - int(time.time()))
        print(f"🚫 Rate limit hit for @{username}. Skipping user. Retry after {wait_seconds}s.")
        
        # Convert to KST (UTC +9)
        reset_time = datetime.fromtimestamp(reset, timezone.utc) + timedelta(hours=9)
        reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"🕒 Rate limit will reset at: {reset_time_str} KST")
        
        return None
    except tweepy.TweepyException as e:
        print(f"❌ Failed to fetch user ID for @{username}: {e}")
        return None

def fetch_latest_tweets(username, limit):
    try:
        # 파일에서 user_id를 읽기
        USER_IDS = load_json(USER_ID_FILE)

        user_id = USER_IDS.get(username)  # 파일에서 가져온 user_id
        if not user_id:
            print(f"📊 Fetching UserID of Username: @{username}")
            user_id = fetch_user_id(username)
            if user_id:
                USER_IDS[username] = user_id  # 새로운 user_id는 저장해서 나중에 사용
                save_json(USER_IDS, USER_ID_FILE)

        if not user_id:
            return None  # user_id가 없으면 데이터가 없다고 처리
     
        since_id = load_last_seen_id(username)
        params = {"id": user_id, "max_results": limit} 
        if since_id: 
            params["since_id"] = since_id

        print(f"📊 Processing Username: @{username} / UserID: {user_id} / SinceID: {since_id}") 
     
        response = client_twitter_read.get_users_tweets(**params)
        tweets_data = response.data or []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 📊 @{username}: {len(tweets_data)} tweets fetched.")
        tweets = [(tweet.id, tweet.text) for tweet in tweets_data]

        if tweets_data:
            latest_id = max(tweet.id for tweet in tweets_data)
            save_last_seen_id(username, latest_id)

        return tweets

    except tweepy.TooManyRequests as e:
        reset = int(e.response.headers.get("x-rate-limit-reset", time.time() + 60))
        wait_seconds = max(0, reset - int(time.time()))
        print(f"🚫 Rate limit hit for @{username}. Skipping user. Retry after {wait_seconds}s.")
        
        # Convert to KST (UTC +9)
        reset_time = datetime.fromtimestamp(reset, timezone.utc) + timedelta(hours=9)
        reset_time_str = reset_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"🕒 Rate limit will reset at: {reset_time_str} KST")

        return None  # ❗️None을 리턴해서 건너뛰도록
    except Exception as e:
        print(f"❌ Twitter fetch failed for {username}: {e}")
        return None

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
    if tweets is None:
        print(f"⏭️ @{username} skipped due to rate limit.\n")
        return  # ❗️이 유저는 건너뜀

    new_posts = []
    for tweet_id, tweet_text in tweets:
        if any(str(tweet['tweet_id']) == str(tweet_id) for tweet in posted_tweets):
            continue

        if not tweet_text.strip():
            print(f"⚠️ Skipping @{username}'s tweet ({tweet_id}) due to empty text.")
            continue

        print(f"🧠 @{username}: {tweet_text}")
        breaking_news = rewrite_as_breaking_news(tweet_text, username, retry=3)
        tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        final_text = f"{breaking_news}\n@{username}\n\n🔗 {tweet_url}"

        success = post_to_twitter(final_text)
        if success:
            new_posts.append({
                "tweet_id": tweet_id,
                "content": breaking_news,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }) 
            wait_with_progress(10) 

    posted_tweets.extend(new_posts)
    save_json(posted_tweets, POSTED_TWEETS_FILE)

def is_within_active_hours(start_time="16:00", end_time="10:00"):
    # Get current time in KST
    kst = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(kst).time()

    start_time_obj = datetime.strptime(start_time, "%H:%M").time()
    end_time_obj = datetime.strptime(end_time, "%H:%M").time()

    if start_time_obj < end_time_obj:
        # Window doesn't cross midnight
        return start_time_obj <= now_kst < end_time_obj
    else:
        # Window crosses midnight
        return now_kst >= start_time_obj or now_kst < end_time_obj

def main_loop():
    print("\n🚀 [START] Serial Twitter Translator + Poster (1 user per minute)")
    posted_tweets = load_json(POSTED_TWEETS_FILE)

    tweet_count_state_file = "tweet_count_state.json"
    tweet_count_state = load_json(tweet_count_state_file)
    last_interim_count = tweet_count_state.get("last_interim_count", 0)
    recent_tweets = []

    is_daily_report_posted = False

    while True:
        if is_within_active_hours("16:00", "10:00"):
            if user_queue:
                username = user_queue.popleft()
                before_count = len(posted_tweets)
                process_user(username, posted_tweets)
                user_queue.append(username)

                new_tweets_slice = posted_tweets[before_count:]
                recent_tweets.extend(new_tweets_slice)

                current_tweet_count = len(posted_tweets)
                new_tweets = current_tweet_count - last_interim_count
                print(f'📊 Keeping track number of new tweets.. : {new_tweets}')
                if new_tweets >= 10:
                    print(f"📊 Posted {new_tweets} new tweets (total: {current_tweet_count}). Posting interim report...")
                    tweets_to_report = recent_tweets[-10:]
                    post_interim_report(new_tweets, tweets_to_report)
                    last_interim_count = current_tweet_count
                    tweet_count_state["last_interim_count"] = last_interim_count
                    save_json(tweet_count_state, tweet_count_state_file)
                    recent_tweets.clear()

                now = datetime.now().strftime("%H:%M")
                daily_report_post_time = "16:30"
                if not is_daily_report_posted and now >= daily_report_post_time:
                    post_summary_report(daily_report_post_time)
                    is_daily_report_posted = True

                reset_time = "05:00"
                if now >= reset_time and now < "05:01":
                    print(f'🔄 Daily Report Flag Time Successfully Reset to {reset_time}')
                    is_daily_report_posted = False

                next_user_delay = random.randint(50, 70)
                print(f"✅ Done with @{username}. Waiting {next_user_delay}s before next user...\n")
                wait_with_progress(next_user_delay)
            else:
                print("🟨 No users in queue. Sleeping for 5 minutes...")
                wait_with_progress(300)
        else:
            print("🌙 Outside active hours (16:00 - 10:00). Sleeping for 10 minutes...")
            wait_with_progress(600)
