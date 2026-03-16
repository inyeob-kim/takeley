import json
from typing import Dict, List

import openai


FORBIDDEN_JARGON = (
    "liquidity sweep",
    "order block",
    "order blocks",
    "ict",
    "institutional positioning",
)


DEFAULT_IMPLICATION_BY_TYPE = {
    "macro": "→ 시장 불확실성이 확대될 수 있음",
    "company": "→ 관련 종목 투자 심리에 영향을 줄 수 있음",
    "market": "→ 단기 변동성이 커질 가능성",
    "breaking": "→ 위험자산 선호 심리가 약해질 수 있음",
    "neutral": "→ 투자 심리 방향을 확인할 필요가 있음",
}


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


def _contains_forbidden_jargon(text: str) -> bool:
    lowered = (text or "").lower()
    return any(term in lowered for term in FORBIDDEN_JARGON)


def _ensure_implication_line(summary: str, news_type: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return summary
    if "→" in summary:
        return summary
    implication = DEFAULT_IMPLICATION_BY_TYPE.get(news_type, DEFAULT_IMPLICATION_BY_TYPE["neutral"])
    return f"{summary}\n{implication}"


def analyze_tweet_for_posting(tweet_text: str, username: str, recent_posts: List[str], retry: int = 2) -> Dict:
    """
    Single-call AI pipeline (cost optimization):
    - relevance/ad filtering
    - similarity check against recent posts
    - Korean breaking-news rewrite
    """
    prompt = f"""
You are the content creator for a Korean financial news account focused on:
- US stocks
- AI sector
- Tesla
- global macro news
- market sentiment

Your task is NOT to translate tweets.
Your task is to convert raw market tweets into short Korean market news posts that add value for general investors.

Task:
1) Determine if the source tweet is relevant for investors.
2) Check if it is reporting the same concrete event as recent posts.
3) If relevant and not similar, write a concise Korean market-insight post.
4) Classify accepted tweet into a news type.
5) Optionally generate one discussion question (about 60% probability).

Return ONLY JSON with this schema:
{{
  "is_relevant": true/false,
  "is_similar": true/false,
  "summary": "string",
  "news_type": "macro|company|market|breaking|neutral",
  "engagement_type": "reply|none",
  "engagement": "string or empty",
  "skip_reason": "duplicate_topic|advertisement|irrelevant|other|none"
}}

Summary format (STRICT):
1) First line: breaking indicator with one emoji (e.g. "⚡ 속보", "📈 시장 속보")
2) Next 1-2 lines: clear Korean summary of the news
3) One implication line that starts with "→"
   - Explain what the news might mean for investors in simple language
   - Maximum one sentence
   - Examples:
     "→ 투자 심리가 위축될 수 있다는 신호"
     "→ 단기 변동성이 커질 가능성"
     "→ 기술주에 긍정적인 신호"
     "→ 시장 불확실성이 확대될 수 있음"
4) Optional hashtags (0-3) may be included at end of summary

Critical language constraints:
- Never use complex trading jargon, including:
  "liquidity sweep", "order blocks", "ICT", "institutional positioning"
- Prefer simple concepts:
  investor sentiment, market volatility, risk appetite, short-term reaction, impact on stocks/market
- Keep Korean clear and understandable for general investors

Question (engagement) rules:
- engagement should be either empty or one short Korean discussion question
- do not force question on every post (target around 60%)
- avoid spammy bait and exaggerated hype

General rules:
- Treat promotions, giveaways, pure links, and unrelated chatter as irrelevant
- Similar means same concrete event/news, not broad topic overlap
- If skipped, summary="", engagement="", engagement_type="none"
- Do not invent facts
- Keep numbers/dates exact when present
- Keep professional tone and concise wording
- Do NOT include source attribution in summary or engagement

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
            if engagement_type not in {"reply", "none"}:
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
            else:
                summary = _ensure_implication_line(summary, news_type)
                if _contains_forbidden_jargon(summary) or _contains_forbidden_jargon(engagement):
                    raise ValueError("Forbidden jargon detected in generated text")

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
