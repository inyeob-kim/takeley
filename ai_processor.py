import json
from typing import Dict, List

import openai


def _extract_json(text: str) -> Dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in AI response")
    return json.loads(text[start : end + 1])


def analyze_tweet_for_posting(tweet_text: str, username: str, recent_posts: List[str], retry: int = 2) -> Dict:
    """
    Single-call AI pipeline (cost optimization):
    - relevance/ad filtering
    - similarity check against recent posts
    - Korean breaking-news rewrite
    """
    prompt = f"""
You are a strict financial news processor.

Task:
1) Determine if this source tweet is relevant for investors.
2) Check if it is reporting the same event as any recent posts.
3) If relevant and not similar, rewrite it in Korean breaking-news style.
4) Classify the accepted tweet into a news type.
5) Choose an engagement strategy type.
6) Generate one natural engagement line only when appropriate.

Return ONLY JSON with this schema:
{{
  "is_relevant": true/false,
  "is_similar": true/false,
  "summary": "string",
  "news_type": "macro|company|market|breaking|neutral",
  "engagement_type": "reply|repost|follow|none",
  "engagement": "string or empty",
  "skip_reason": "duplicate_topic|advertisement|irrelevant|other|none"
}}

Rules:
- Treat promotions, giveaways, pure links, and unrelated chatter as irrelevant.
- Similar means same concrete event/news, not broad topic overlap.
- If skipped, summary="", engagement="", engagement_type="none".
- If accepted, summary must be Korean, factual, concise, with natural emojis (2-3 max), and include key numbers/dates exactly.
- Engagement must be either an empty string or a single short Korean line.
- Do not invent facts.
- Keep numbers/dates exact when present.

News type definitions:
- macro: CPI, inflation, jobs, rates, Fed, central bank, bonds, macro economy
- company: Tesla, Nvidia, Apple, earnings, guidance, launches, company announcements
- market: price action, broad market moves, futures, indexes, sector moves
- breaking: war, geopolitical escalation, emergency policy, major shock events
- neutral: relevant but not strong enough for special engagement treatment

Engagement rules:
- The engagement line must feel natural, not spammy.
- Engagement must match the type of news.
- Do not include engagement in every accepted post.
- Avoid repeating the same wording too often.
- Keep wording short and native-sounding in Korean.
- Encourage interaction without low-quality engagement bait.

Strategy by news_type:
- macro: prefer discussion/interpretation questions (engagement_type usually "reply")
  examples: "여러분은 이번 지표 어떻게 해석하시나요?" / "금리 인하 기대는 아직 유효하다고 보시나요?"
- company: prefer opinion questions (engagement_type usually "reply")
  examples: "이 이슈, 주가에 호재라고 보시나요?" / "여러분은 이 발표를 어떻게 보시나요?"
- market: prefer trader discussion prompts (engagement_type usually "reply")
  examples: "지금 시장 방향 어떻게 보고 계신가요?" / "트레이더 여러분 의견이 궁금합니다."
- breaking: prefer repost/share prompts (engagement_type often "repost")
  examples: "중요한 뉴스라면 리포스트로 공유해주세요 🔁" / "트레이더들에게 중요한 이슈입니다. 공유해주세요."
- neutral: usually no engagement; rarely a follow prompt
  examples: "실시간 시장 속보를 보려면 팔로우하세요." / "글로벌 금융 속보 계속 보시려면 팔로우 🔔"

Probability-style rules:
- Reply-style engagement should be most common.
- Repost prompts should be reserved for high-impact news.
- Follow prompts should be rare.
- If the news is minor, set engagement_type="none" and engagement="".

Username: @{username}
Source tweet:
\"\"\"{tweet_text}\"\"\"

Recent posts:
{json.dumps(recent_posts[-10:], ensure_ascii=False)}
"""

    last_error = None
    for attempt in range(retry):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = response.choices[0].message.content.strip()
            data = _extract_json(content)
            news_type = str(data.get("news_type", "neutral")).strip().lower()
            if news_type not in {"macro", "company", "market", "breaking", "neutral"}:
                news_type = "neutral"

            engagement_type = str(data.get("engagement_type", "none")).strip().lower()
            if engagement_type not in {"reply", "repost", "follow", "none"}:
                engagement_type = "none"

            summary = str(data.get("summary", "")).strip()
            engagement = str(data.get("engagement", "")).strip()

            # Guardrails: if skipped/irrelevant/similar, force no engagement payload.
            is_relevant = bool(data.get("is_relevant", False))
            is_similar = bool(data.get("is_similar", False))
            if (not is_relevant) or is_similar:
                summary = ""
                engagement = ""
                engagement_type = "none"

            return {
                "ok": True,
                "is_relevant": is_relevant,
                "is_similar": is_similar,
                "summary": summary,
                "news_type": news_type,
                "engagement_type": engagement_type,
                "engagement": engagement,
                "skip_reason": str(data.get("skip_reason", "other")).strip() or "other",
            }
        except Exception as e:
            last_error = e
            print(f"[AI] failed attempt={attempt + 1}/{retry} error={e}")
    return {
        "ok": False,
        "is_relevant": False,
        "is_similar": False,
        "summary": "",
        "news_type": "neutral",
        "engagement_type": "none",
        "engagement": "",
        "skip_reason": "ai_error",
        "error": str(last_error) if last_error else "unknown",
    }
