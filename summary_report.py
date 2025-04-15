import openai
import tweepy
import openai
import os
import json
from config import set_environment
from tqdm import tqdm
from datetime import datetime, timedelta, time  # Add 'time' here

 

# 🔧 Load environment variables 
set_environment()
 
# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

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

def filter_tweets_by_time(tweets):
    filtered_tweets = []

    for tweet in tweets: 
        tweet_time = datetime.strptime(tweet['time'], "%Y-%m-%d %H:%M:%S").time()

        evening_start = time(16, 30)  # 16:30 PM  
        early_morning_end = time(5, 0)  # 5:00 AM

        if tweet_time >= evening_start or tweet_time < early_morning_end:
            filtered_tweets.append(tweet)

    return filtered_tweets

def summarize_tweets(tweets):
    """
    Summarizes tweets into a clear, structured daily report for investors with light emojis and analysis.
    """
    tweet_texts = [tweet['content'] for tweet in tweets]
    combined_text = " ".join(tweet_texts)

    prompt = f"""
        📰 **데일리 투자 리포트** 

        너는 월가의 투자 전문가로서, 어제 하루 동안 발생한 글로벌 금융 및 경제 뉴스를 분석해주는 역할을 맡고 있어.

        아래 트윗 내용을 바탕으로 투자자들이 쉽게 이해할 수 있도록 정리해줘:
        - 핵심 뉴스는 주제별로 구분하여 정리 (예: 금리, 주식시장, 지정학적 이슈 등)
        - 각 항목은 2~4문장 정도로 명확하게 설명
        - 너무 많은 이모지 ❌ / 각 주제 앞에 어울리는 이모지 ✅ (예: 📈 시장, 🏦 금리, ⚠️ 리스크, 💬 정책 등)
        - 마지막에는 "**내일을 위한 인사이트 🔮**" 섹션을 만들어 향후 예상되는 이슈나 주목할 점을 요약

        다음은 어제의 트윗 뉴스입니다:
        {combined_text}

        이 내용을 바탕으로, 아래 형식으로 리포트를 작성해주세요:

        ---

        📌 **데일리 투자 리포트** 
        1. [주제명] 이모지 + 제목  
        - 요약된 내용

        ...

        🔮 **내일을 위한 인사이트**
        - 예상되는 시장 반응 및 주의할 이슈 요약

        ---

        투자자들이 이 정보를 바탕으로 전략을 세울 수 있도록 도와주세요.
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.choices[0].message.content.strip()
        print(f"📢 Final Summary:\n{summary}")
        return summary
    except Exception as e:
        print(f"❌ Failed to summarize tweets: {e}")
        return "뉴스 요약 실패"
    
def post_interim_report(tweet_count, recent_tweets):

    tweet_texts = [tweet['content'] for tweet in recent_tweets]
    combined_text = " ".join(tweet_texts)

    prompt = f"""
        📢 **중간 뉴스 리포트**

        너는 월가의 투자 전문가로, 최근 {tweet_count}개의 금융 및 경제 뉴스 트윗을 분석해 투자자들에게 빠르게 전달하는 역할을 맡고 있어.

        아래 트윗 내용을 바탕으로 투자자들이 이해하기 쉽게 정리해줘:
        - 핵심 뉴스를 최대 2개 주제로 나누어 요약 (예: 금리, 주식시장 등)
        - 각 주제는 1~2문장으로 간결히 설명
        - 이모지는 주제 앞에 하나만 사용 (예: 📈 시장, 🏦 금리, ⚠️ 리스크)
        - 마지막에 "**다음 업데이트 기대점 🔮**"로 간단한 전망 (1문장)
        - 출력은 한글로, 명확하고 전문적으로

        최근 트윗:
        {combined_text}

        출력 형식:
        ---
        📢 **중간 뉴스 리포트** ({tweet_count}개 트윗)
        1. [주제] 이모지 + 제목
        - 내용
        2. [주제] 이모지 + 제목
        - 내용 
        🔮 **다음 업데이트 기대점**
        - 전망
        ---
        #주식이미쳤다 #금융속보
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        report_text = response.choices[0].message.content.strip()
        client_twitter.create_tweet(text=report_text)
        print(f"Interim report posted for {tweet_count} tweets:\n{report_text}")
        print(f'📊📌 Interim Report Posted for {tweet_count}!!')
    except Exception as e:
        print(f"❌ Failed to post interim report: {e}") 


# 트윗 작성
def post_to_twitter(text, max_retries=3):
    for attempt in range(max_retries):
        try:
            client_twitter.create_tweet(text=text)
            print(f'📌📌📌📌📌 Daily Report Posted!! 📌📌📌📌📌')
            return True
        except Exception as e:
            print(f"❌ Tweet post failed: {e}")
            time.sleep(5)
    return False

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load {filename}: {e}")
        return {}
    
def wait_with_progress(seconds): 
    for _ in tqdm(range(seconds), desc=f"⏳ Waiting {seconds}s", unit="s"):
        time.sleep(1)

def post_summary_report(post_time="16:30"): 
    """ 
    Schedules the summary post for the given time (post_time) on the next day.
    `post_time` should be in HH:MM format, e.g., "16:30" for 4:30 PM.
    """
    # Split the post_time into hours and minutes
    post_hour, post_minute = map(int, post_time.split(":"))

    now = datetime.now() 
    next_post_time = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1, hours=post_hour, minutes=post_minute)
    time_to_wait = (next_post_time - now).total_seconds()
    print(f"Next Post Time : {next_post_time} / Time to Wait : {time_to_wait}")
 
    # After waiting, summarize and post the tweets from the specified ti me range
    posted_tweets = load_json(POSTED_TWEETS_FILE)  # Load previously posted tweets
    filtered_tweets = filter_tweets_by_time(posted_tweets)  # Filter tweets from 4:30 PM to 5:00 AM

    if not filtered_tweets:
        print(f'⚠️ There are NO filtered tweets to post Daily Report!')
        return 
    
    summary = summarize_tweets(filtered_tweets)  # Summarize the filtered tweets
    
    success = post_to_twitter(summary)  # Use the post_to_twitter function from your code
    if success:
        print(f"🐦 Summary posted to Twitter!")
    else: 
        print(f"❌ Failed to post the summary.")

    wait_with_progress(10)
