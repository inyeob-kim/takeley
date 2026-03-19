import openai
import tweepy
import os
import random
import re
from difflib import SequenceMatcher
from config import set_environment

 

# 🔧 Load environment variables 
set_environment()
 
# 🔑 API Keys
openai.api_key = os.getenv("OPENAI_API_KEY")

client_twitter = tweepy.Client( 
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"), 
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)

INTERIM_KEYWORDS = ("fed", "inflation", "oil", "ai", "war", "earnings")

def _clean_news_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_score(text: str) -> int:
    lowered = (text or "").lower()
    return sum(1 for keyword in INTERIM_KEYWORDS if keyword in lowered)


def _is_similar_text(a: str, b: str, threshold: float = 0.9) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def _prepare_interim_inputs(recent_tweets, max_items: int = 20):
    base_items = []
    for item in recent_tweets[-max_items:]:
        content = _clean_news_text(str(item.get("content", "")))
        if content:
            base_items.append(content)

    if not base_items:
        return []

    # Prioritize market-moving keyword hits first, then preserve recency among ties.
    indexed = list(enumerate(base_items))
    indexed.sort(key=lambda pair: (_keyword_score(pair[1]), pair[0]), reverse=True)

    deduped = []
    for _, text in indexed:
        if any(_is_similar_text(text, existing) for existing in deduped):
            continue
        deduped.append(text)
        if len(deduped) >= max_items:
            break
    return deduped


def _pick_interim_header() -> str:
    return "📈 장중 핵심 3줄" if random.random() < 0.7 else "📊 오늘 시장 핵심"


def _build_interim_prompt(news_items, header: str, strict_mode: bool = False) -> str:
    strict_block = """
If the draft may exceed the limit, you must:
- keep the same format
- compress wording only
- remove weak modifiers
- do not add explanation
- target under 240 characters total
""".strip() if strict_mode else ""

    return f"""
You are a financial news summarizer for retail investors.
Write a short Korean market brief for X.

Task:
- Extract ONLY the 3 most important market-driving themes from the input news
- The 3 lines should reflect the dominant market themes, not just any 3 headlines
- Prefer themes that explain today's market tone over isolated company updates
- If multiple inputs are about the same theme, merge them into one broader market-driving topic
- Merge similar topics
- Ignore minor, repetitive, or low-impact headlines
- Prioritize themes that can move rates, oil, AI, geopolitics, major tech, or broad risk sentiment

Output format (strict):
{header}
1. [핵심 이슈 1]
2. [핵심 이슈 2]
3. [핵심 이슈 3]

→ [시장 한 줄 해석]

Rules:
- Korean only
- No extra explanation
- No emojis except the header
- Keep each numbered line concise and natural
- Keep total output under 280 characters
- Make the final line useful for investors
- The final line must describe the market tone or pressure point for investors
- The final line must explain what is driving sentiment, not simply restate the 3 headlines
- Avoid vague wording like "영향이 있을 수 있음", "변동성 확대", "불확실성 증가" unless unavoidable

Preferred final-line styles:
- 위험자산 선호 회복 시도
- 유가 변수 재부각
- 금리 경계감이 시장 상단 제약
- AI 기대가 기술주 심리 지지
- 지정학 리스크가 투자심리 압박
- 관망 심리가 강한 장세

{strict_block}

Input news:
{chr(10).join(f"- {item}" for item in news_items)}
""".strip()


def _safe_truncate_report(text: str, max_len: int = 280) -> str:
    if len(text) <= max_len:
        return text

    hard_cut = text[:max_len].rstrip()

    # Prefer cutting at line boundaries first to keep the 3-line structure readable.
    line_cut = hard_cut.rfind("\n")
    if line_cut >= 0:
        candidate = hard_cut[:line_cut].rstrip()
        if candidate:
            return candidate

    # Fallback: cut at punctuation boundary.
    punctuation_cut = max(hard_cut.rfind("."), hard_cut.rfind("!"), hard_cut.rfind("?"), hard_cut.rfind("다"))
    if punctuation_cut > 0:
        return hard_cut[: punctuation_cut + 1].rstrip()

    return hard_cut


def post_interim_report(tweet_count, recent_tweets):
    news_items = _prepare_interim_inputs(recent_tweets, max_items=20)
    if not news_items:
        print("[REPORT] interim_skipped reason=no_valid_input")
        return

    header = _pick_interim_header()
    prompt = _build_interim_prompt(news_items, header=header, strict_mode=False)
    report_text = ""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        report_text = response.choices[0].message.content.strip()
        print(f"[REPORT] interim_generated length={len(report_text)} retry=0")

        if len(report_text) > 280:
            retry_prompt = _build_interim_prompt(news_items, header=header, strict_mode=True)
            print("[REPORT] interim_retry reason=length_exceeded")
            retry_response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": retry_prompt}]
            )
            report_text = retry_response.choices[0].message.content.strip()
            print(f"[REPORT] interim_generated length={len(report_text)} retry=1")

        if len(report_text) > 280:
            report_text = _safe_truncate_report(report_text, max_len=280)
            print(f"[REPORT] interim_truncated final_length={len(report_text)}")

        client_twitter.create_tweet(text=report_text)
        print(f"[REPORT] interim_posted tweets={tweet_count} final_length={len(report_text)}")
        print(f"[REPORT] interim_text={report_text}")
    except Exception as e:
        print(f"❌ Failed to post interim report: {e}") 


