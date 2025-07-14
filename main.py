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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# 🔧 Load environment variables 
set_environment()

# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY") 
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# email
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # Your sender email
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Your email app password or actual password
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")  # Destination email
 
# 사용자 큐 설정
user_queue = deque(["Investingcom", "DeItaone", "BRICSinfo", "TheSonOfWalkley", "SawyerMerritt"]) 

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

    ⚠️ 중요 지침:

    1. **첫 줄은 고정된 헤드라인 없이**, 핵심 사건을 요약한 강렬한 문장으로 시작  
    - 예: "⚡ 속보: 파월, 금리 인하 시사…시장 기대감 폭발"

    2. 핵심 인물 또는 기관 + 행동/사건 요약 → **무슨 일이 벌어졌는지 구체적으로 설명**
 
    3. **시간 흐름, 정보 흐름**에 따라 정돈된 문단 구성  
    - 예: 사건 발생 → 영향 → 관련 배경

    4. 일정, 실적, 출시 등 숫자나 날짜 정보는 **절대 요약하지 말고 원문 그대로 정확하게 번역**  
    - ❌ 요약 예: "중요한 발표", "일정 공유"
    - ✅ 바른 예: "로보택시, 8월 8일 공개 예정", "2분기 매출 2.45억 달러, 전년 대비 12% 증가"
    - 🔥 반드시 **트윗 속 숫자와 표현을 한 글자도 빠짐없이** 반영할 것

    5. URL 링크뿐인 트윗은 그대로 ⬇️⬇️⬇️ 리턴

    6. 트윗이 특정 **상장 기업**과 직접적 관련 있을 경우, 본문 중 적절히 **티커 ($TSLA $NVDA)** 삽입  
    - 무관하면 티커 생략

    7. 분위기와 맥락에 어울리는 **이모지 2~3개 자연스럽게 활용**  
    - 과도한 이모지 금지

    8. **추측 일절 금지. 오직 객관적 분석 및 해석, 사실만 전달**

    9. **현재 미국 대통령은 도널드 트럼프입니다. (전 대통령 아님)**

    ---
    \"{text}\"  


    출력 형식 예시:

    ⚡ 속보: JP모건 “경기침체 피할 수 없다” 경고  

    글로벌 증시 일제히 하락세 📉  
    美 채권 수익률 급락, 달러 강세 반전  
    투자자들 안전자산 선호 심화  

    $JPM $DIA  

    #JP모건 #침체경고 #시장분석 #BreakingNews  


    출력 형식:

    티커 존재 시:  
    [⚡ 속보: + 핵심 문장]  

    [본문]  

    $TSLA $NVDA (티커 여러 개 가능)  

    #Hashtag1 #Hashtag2 #Hashtag3 #BreakingNews  

    티커 없을 시:  
    [⚡ 속보: + 핵심 문장]  

    [본문]  

    #Hashtag1 #Hashtag2 #Hashtag3 #BreakingNews  
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

def is_irrelevant_or_ad(tweet_text, username):

    # skips checking similar post for TrumpDailyPosts.
    if username == "TrumpDailyPosts":
        return False

    prompt = (
        "You are a smart assistant that classifies tweets based on their relevance to financial investors.\n"
        "If the tweet is promotional, advertising, or unrelated to finance, economics, political, or investment insights, respond with 'YES'.\n"
        "Otherwise, respond with 'NO'.\n\n"
        f"Tweet:\n{tweet_text}\n\n"
        "Is this tweet irrelevant or promotional?"
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content.strip()

    return result.upper() == "YES"


def is_similar_to_recent(new_text, recent_texts, username):
    # Skip checking for specific usernames
    if username == "TrumpDailyPosts":
        return False

    prompt = (
        "You are an assistant that checks if a new social media post is reporting the same news as any recent posts. "
        "Two posts are considered similar **only** if they are about the exact same event or news topic, "
        "even if the wording is different. Do not consider general themes or opinions—focus only on whether "
        "the actual subject of the news is the same.\n\n"
        f"New Post:\n{new_text}\n\n"
        f"Recent Posts:\n" +
        "\n---\n".join(recent_texts) +
        "\n\nIs the new post reporting the same news as any of the previous posts? Respond only with 'YES' or 'NO'."
    )
 
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.choices[0].message.content.strip()

    return result.upper() == "YES"



# 사용자별 트윗 처리 
def process_user(username, posted_tweets, num_posted):
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

        # ❌ Skip if tweet is ad/promotional/unrelated except Donald Trump Tweet
        if is_irrelevant_or_ad(tweet_text, username):
            print(f"🧹 Skipping @{username}'s tweet ({tweet_id}) below — Reason: detected as irrelevant or ad.")
            print(f"🧹 Skipped Tweet:\n{tweet_text} ")
            continue

        print(f"🧠 @{username}: {tweet_text}")
        breaking_news = rewrite_as_breaking_news(tweet_text, username, retry=3)

        # 🔍 Check for similarity in recent posts -> if similar tweet already posted -> skip posting
        recent_posts = [p["content"] for p in posted_tweets[-10:]]
        if is_similar_to_recent(breaking_news, recent_posts, username): # except Donald Trump Tweet
            print(f"🛑 Skipping tweet ({tweet_id}) — similar content already posted.")
            continue 
 
        # tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
        # final_text = f"{breaking_news}\n@{username}\n\n🔗 {tweet_url}"

        final_text = f"{breaking_news}\n" 

        success = post_to_twitter(final_text) 
        if success:
            new_posts.append({
                "tweet_id": tweet_id,
                "content": breaking_news,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }) 
            wait_with_progress(10) 

    posted_tweets.extend(new_posts)
    num_posted = num_posted + 1
    save_json(posted_tweets, POSTED_TWEETS_FILE)

def is_within_active_hours(start_time="16:00", end_time="10:00", test_mode=False):

    if test_mode:
        return True

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
    
from datetime import datetime, timedelta
import pytz
import os

def parse_time_str(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"❌ 시간 파싱 오류: {s} -> {e}")
        return None

def generate_youtube_script():
    print("🎥 Generating YouTube script for today’s summary video...")
    try:
        posted_tweets = load_json(POSTED_TWEETS_FILE)
        kst = pytz.timezone("Asia/Seoul")
        now_kst = datetime.now(kst)

        today_date = now_kst.date()
        yesterday_date = today_date - timedelta(days=1)

        # start_time: 어제 22:00
        start_time = datetime.combine(yesterday_date, datetime.min.time(), tzinfo=kst).replace(hour=22)
        # end_time: 오늘 06:00
        end_time = datetime.combine(today_date, datetime.min.time(), tzinfo=kst).replace(hour=6)

        # 비교할 때는 tzinfo 제거 (기존 코드 방식 유지)
        start_time_naive = start_time.replace(tzinfo=None)
        end_time_naive = end_time.replace(tzinfo=None)

        print("filtered time range:") 
        print("start_time =", start_time_naive)
        print("end_time   =", end_time_naive)

        filtered_tweets = []
        for t in posted_tweets:
            tweet_time = parse_time_str(t.get("time", ""))
            if tweet_time is None:
                continue
            if start_time_naive <= tweet_time <= end_time_naive:
                filtered_tweets.append(t) 

        print("✅ total posted tweets len =", len(posted_tweets))
        print("✅ filtered tweets len =", len(filtered_tweets))

        # 뉴스 내용 정리
        contents = "\n".join([f"- {t['content']}" for t in filtered_tweets])

        # OpenAI 프롬프트
        prompt = f"""
                당신은 ‘주식이 미쳤다 뉴스’라는 글로벌 금융 속보 채널의 유튜브 콘텐츠 기획자이자 대본 작성자입니다.

                아래는 최근 12시간 동안 수집된 금융 뉴스 트윗 요약입니다.
                이 중에서 **실제로 투자자에게 중요한 뉴스**만을 추려, 아래 포맷에 맞춰 **하루 1편 영상용 대본**을 작성하세요.

                ⚠️ 중요 지침:

                1. **투자자와 글로벌 금융 종사자가 관심 가질만한 뉴스만 반영**
                    - 미국 경제지표 (CPI, PPI, 고용, 연준 관련)
                    - 주요 기업 실적 (TSLA, NVDA, AAPL 등)
                    - 금리 정책, 통화정책, 지정학 이슈
                    - 산업 흐름 (AI, 반도체, 전기차, 원유 등)
                    - 실질적 시장에 영향 주는 사건 중심 (루머/사견/광고 제외)

                2. **뉴스 요약은 오로지 사실 중심**으로 작성하며 과장 금지  
                    - 숫자/날짜/수치 누락 없이 정확히 사용

                3. **전체 분량은 약 5분 분량의 유튜브 영상 스크립트로 구성**

                ---

                🎬 유튜브 영상 포맷:

                인트로 (5초):  
                “⚡ 글로벌 금융 속보 — 지금 바로 확인하세요!”

                헤드라인 (30초):  
                오늘의 핵심 키워드 3가지를 뽑아 간결하게 요약

                본문 요약 (4분):  
                각 뉴스에 대해 ‘무슨 일이 일어났고 왜 중요한지’를 설명  
                투자자 입장에서 가장 중요한 맥락만 정리

                클로징 (20초):  
                내일 주목할 이벤트 1~2개 + 구독 유도 멘트

                ---

                아래는 오늘 들어온 뉴스입니다:  
                {contents}
            """

        # GPT 호출
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        script = response.choices[0].message.content.strip()

        # ✅ 저장 (.txt 파일로 저장)
        filename = "youtube_script.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(script)

        print(f"✅ YouTube script generated and saved to {filename}:\n")
        print(script)

        # 이메일 자동 전송
        send_script_email(script)

        return script

    except Exception as e:
        print(f"❌ Failed to generate YouTube script: {e}")
        return None


def send_script_email(script_text):
    msg = MIMEMultipart()
    msg["Subject"] = "오늘의 유튜브 요약 스크립트"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECEIVER

    # Email body
    body = f"안녕하세요,\n\n오늘 생성된 유튜브 대본입니다:\n\n{script_text}\n\n감사합니다."
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
 
def main_loop(test_mode=False):
    print("\n🚀 [START] Serial Twitter Translator + Poster (1 user per minute)")
    posted_tweets = load_json(POSTED_TWEETS_FILE)

    tweet_count_state_file = "tweet_count_state.json"
    tweet_count_state = load_json(tweet_count_state_file)
    last_interim_count = tweet_count_state.get("last_interim_count", 0)
    recent_tweets = []

    ACTIVE_HOUR_START_TIME = "16:30"  
    ACTIVE_HOUR_END_TIME = "8:00"  

    is_daily_report_posted = False 
    DAILY_REPORT_POST_TIME_START = "16:30"
    DAILY_REPORT_POST_TIME_END = "17:00"
    DAILY_REPORT_RESET_TIME = "05:00"

    total_num_posts_today = 0

    is_daily_script_sent = False  # ✅ 6시 스크립트 전송 여부 플래그

    if test_mode:
        # Generate YouTube script immediately
        generate_youtube_script()
        print("✅ Test mode active: YouTube script generated immediately.")
        return  # Optionally exit after test run

    while True: 
        
        if not is_within_active_hours(ACTIVE_HOUR_START_TIME, ACTIVE_HOUR_END_TIME, test_mode=True): # if test_mode = True, it always returns True
            active_hour_delay = 60 
            print(f"🌙 Outside active hours ({ACTIVE_HOUR_START_TIME}pm - {ACTIVE_HOUR_END_TIME}am the next day). Sleeping for {active_hour_delay} seconds...")
            wait_with_progress(active_hour_delay)
            continue

        if user_queue:
            username = user_queue.popleft()
            before_count = len(posted_tweets) 
            process_user(username, posted_tweets, total_num_posts_today)
            user_queue.append(username)

            new_tweets_slice = posted_tweets[before_count:]
            recent_tweets.extend(new_tweets_slice)

            current_tweet_count = len(posted_tweets)
            new_tweets = current_tweet_count - last_interim_count 
            print(f'📊 Keeping track number of new tweets.. : {new_tweets}')
            new_tweet_range = 20 # when number of recent new tweets reaches 20
            if new_tweets >= new_tweet_range: # every new_tweet_range tweets it gives interim report to users... 
                print(f"📊 Posted {new_tweets} new tweets (total: {current_tweet_count}). Posting interim report...")
                tweets_to_report = recent_tweets[-new_tweet_range:]
                post_interim_report(new_tweets, tweets_to_report)
                last_interim_count = current_tweet_count
                tweet_count_state["last_interim_count"] = last_interim_count
                save_json(tweet_count_state, tweet_count_state_file)
                recent_tweets.clear()
 
            # now = datetime.now().strftime("%H:%M")
            # if not is_daily_report_posted and "16:30" <= now < "17:00":
            #     post_report_result = post_summary_report()
            #     if post_report_result:
            #         is_daily_report_posted = True

            # if now >= DAILY_REPORT_RESET_TIME and now < "05:10": 
            #     print(f'🔄 Daily Report Flag Time Successfully Reset to {DAILY_REPORT_RESET_TIME}')
            #     is_daily_report_posted = False

            # print(f"✅ Daily Report Posted : {is_daily_report_posted}\n")

            # next_user_delay = random.randint(60, 90) 
            next_user_delay = 60  
            print(f"✅ Done with @{username}. Waiting {next_user_delay}s before next user...")
            print(f"✅ Total number of posts: {total_num_posts_today}\n")
            wait_with_progress(next_user_delay)

            # ✅ 매일 06:00 ~ 06:10 사이에 1회만 실행
            kst = pytz.timezone("Asia/Seoul")
            now_kst = datetime.now(kst)
            now_time = now_kst.strftime("%H:%M")

            if "06:00" <= now_time < "06:20" and not is_daily_script_sent:
                print("🕕 06:00~06:20 범위 진입 — 유튜브 스크립트 생성 및 이메일 전송")
                generate_youtube_script()
                is_daily_script_sent = True
 
            elif now_time >= "06:20":
                is_daily_script_sent = False

        else:
            print("🟨 No users in queue. Sleeping for 5 minutes...")
            wait_with_progress(300)


if __name__ == "__main__":
    main_loop()
