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


def analyze_tweet_for_posting(
    tweet_text: str,
    username: str,
    recent_posts: List[str],
    recent_implications: List[str] | None = None,
    recent_engagements: List[str] | None = None,
    retry: int = 2,
) -> Dict:
    """
    Single-call AI pipeline (cost optimization):
    - relevance/ad filtering
    - similarity check against recent posts
    - Korean investor-friendly rewrite
    - implication/format/engagement generation
    """
    recent_implications = recent_implications or []
    recent_engagements = recent_engagements or []
    prompt = f"""
You are a strict financial news processor.
You write Korean market updates for general investors.

Task:
1) Determine if this source tweet is relevant for investors.
2) Check if it is reporting the same event as any recent posts.
3) If relevant and not similar, write a concise Korean summary with a natural breaking header.
4) Add a simple investor-friendly implication when appropriate.
5) Choose one format type.
6) Add one short engagement line only when appropriate.

Return ONLY JSON with this schema:
{{
  "is_relevant": true/false,
  "is_similar": true/false,
  "summary": "string",
  "implication": "string",
  "format_type": "news_only|news_implication|news_implication_question|news_implication_repost",
  "engagement": "string",
  "news_type": "macro|company|market|breaking|neutral",
  "skip_reason": "duplicate_topic|advertisement|irrelevant|other|none"
}}

Rules:
- Treat promotions, giveaways, pure links, and unrelated chatter as irrelevant.
- Similar means same concrete event/news, not broad topic overlap.
- If skipped, summary="", implication="", engagement="", format_type="news_only".
- If accepted, summary must be Korean, factual, concise, and include key numbers/dates exactly.
- Summary should start with one of these openers only when natural: "⚡ 속보", "📈 시장 속보", "🚨 긴급".
- implication must be either empty or one short sentence that starts with "→".
- implication must use simple investor language (sentiment, volatility, uncertainty, risk appetite, short-term pressure).
- Avoid jargon like liquidity sweep, order block, ICT, institutional positioning, liquidity grab, smart money.
- engagement must be either empty or one short Korean line.
- Do not invent facts.
- Keep numbers/dates exact when present.
- Tone: fast, clear, investor-friendly, professional. Avoid meme-like or sensational tone.

News type definitions:
- macro: CPI, inflation, jobs, rates, Fed, central bank, bonds, macro economy
- company: Tesla, Nvidia, Apple, earnings, guidance, launches, company announcements
- market: price action, broad market moves, futures, indexes, sector moves
- breaking: war, geopolitical escalation, emergency policy, major shock events
- neutral: relevant but not strong enough for engagement

Format rules (target mix, do not force):
- news_implication: most common (about 40%)
- news_implication_question: second most common (about 35%)
- news_only: less common (about 15%)
- news_implication_repost: rare (about 10%) and only for high-impact macro/breaking
- Never force every post to end with a question.

Format constraints:
- news_only: summary only, implication="", engagement=""
- news_implication: summary + implication, engagement=""
- news_implication_question: summary + implication + short discussion question
- news_implication_repost: summary + implication + short repost/share CTA
- Follow CTA should be very rare; prefer discussion questions when engagement is needed.

Recent wording to avoid repeating too often:
- recent implications: {json.dumps(recent_implications[-8:], ensure_ascii=False)}
- recent engagements: {json.dumps(recent_engagements[-8:], ensure_ascii=False)}

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

            summary = str(data.get("summary", "")).strip()
            implication = str(data.get("implication", "")).strip()
            format_type = str(data.get("format_type", "news_implication")).strip().lower()
            engagement = str(data.get("engagement", "")).strip()
            if format_type not in {
                "news_only",
                "news_implication",
                "news_implication_question",
                "news_implication_repost",
            }:
                format_type = "news_implication"

            # Implication must start with arrow when present.
            if implication and not implication.startswith("→"):
                implication = f"→ {implication.lstrip('- ').strip()}"

            # Guardrails: if skipped/irrelevant/similar, force no engagement payload.
            is_relevant = bool(data.get("is_relevant", False))
            is_similar = bool(data.get("is_similar", False))
            if (not is_relevant) or is_similar:
                summary = ""
                implication = ""
                engagement = ""
                format_type = "news_only"
            else:
                # Format hardening to keep assembly stable and avoid malformed payloads.
                if format_type == "news_only":
                    implication = ""
                    engagement = ""
                elif format_type == "news_implication":
                    if not implication:
                        format_type = "news_only"
                    engagement = ""
                elif format_type == "news_implication_question":
                    if not implication:
                        format_type = "news_only"
                        engagement = ""
                    elif not engagement:
                        format_type = "news_implication"
                elif format_type == "news_implication_repost":
                    if not implication:
                        format_type = "news_only"
                        engagement = ""
                    elif not engagement:
                        format_type = "news_implication"

            return {
                "ok": True,
                "is_relevant": is_relevant,
                "is_similar": is_similar,
                "summary": summary,
                "implication": implication,
                "format_type": format_type,
                "news_type": news_type,
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
        "implication": "",
        "format_type": "news_only",
        "news_type": "neutral",
        "engagement": "",
        "skip_reason": "ai_error",
        "error": str(last_error) if last_error else "unknown",
    }
