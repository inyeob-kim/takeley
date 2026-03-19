import json
import re
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


DISALLOWED_GENERIC_TAGS = {"#주식투자", "#경제", "#뉴스"}


def _normalize_hashtags(raw: str, limit: int = 2) -> str:
    tags = []
    seen = set()
    for token in str(raw or "").split():
        if not token.startswith("#"):
            continue
        cleaned_body = re.sub(r"[^0-9A-Za-z가-힣_]", "", token[1:])
        if not cleaned_body:
            continue
        tag = f"#{cleaned_body}"
        lowered = tag.lower()
        if lowered in seen:
            continue
        if tag in DISALLOWED_GENERIC_TAGS:
            continue
        seen.add(lowered)
        tags.append(tag)
        if len(tags) >= limit:
            break
    return " ".join(tags)


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

Your job:
1) Decide whether the source tweet contains investor-relevant new information.
2) Decide whether it is reporting the same concrete event as a recent post.
3) If relevant and not similar, write a concise Korean market update.
4) Add one high-quality investor implication only when the market link is clear.
5) Choose exactly one format type.
6) Add one short engagement line only when it is truly useful.
7) Generate 0-2 hashtags under the hashtag rules.

Return ONLY valid JSON with this schema:
{{
  "is_relevant": true,
  "is_similar": false,
  "summary": "string",
  "implication": "string",
  "format_type": "news_only|news_implication|news_implication_question|news_implication_repost",
  "engagement": "string",
  "hashtags": "string",
  "news_type": "macro|company|market|breaking|neutral",
  "skip_reason": "duplicate_topic|advertisement|irrelevant|other|none"
}}

---

### Decision rules:

- Relevant = news that may affect stocks, sectors, indexes, rates, oil, bonds, FX, geopolitics, or investor sentiment.
- Irrelevant = promotions, giveaways, referrals, jokes, opinions, vague reactions, or no new factual info.
- Treat speculative / rumor-like tweets conservatively.
- If the tweet is mainly opinion, hype, or speculation without a clear factual development, treat it conservatively.
- Prefer factual developments over commentary.
- If a claim appears second-hand or unverified, do not overstate certainty.
- If the source tweet contains vague claims without a concrete update, set is_relevant=false unless clear investor relevance exists.

- Similar = same event, same actor, same core action, same meaning (even if wording differs).
- Not similar = new numbers, new timing, new official statement, or meaningful escalation.

---

### Output rules:

- JSON only. No markdown. No explanation.
- If skipped:
  - summary=""
  - implication=""
  - engagement=""
  - format_type="news_only"
  - skip_reason must be set

- If accepted:
  - skip_reason="none"

---

### Summary rules:

- Korean only
- Factual, concise, natural
- Include key numbers/dates exactly if present
- Do NOT invent facts
- Write like a fast Korean market desk update, not a literal translation.
- Prefer tight phrasing over direct translation.
- Remove filler/reporting verbs when unnecessary.
- Avoid awkward endings like repeated "라고 밝혔다", "라고 말했다" unless truly needed for attribution.

- Use header ONLY when natural:
  - 🚨 긴급 → war, escalation, emergency
  - ⚡ 속보 → important fresh update
  - 📈 시장 속보 → market moves

- Avoid unnecessary wording like:
  - "라고 밝혔습니다" (remove filler)
  - keep sentences tight

---

### Implication rules (CRITICAL):

- Must start with "👉" or be empty
- MUST explain WHY this matters (not just that it matters)
- MUST be specific and differentiated
- MUST avoid generic phrases:
  - "긍정적인 영향"
  - "부정적인 영향"
  - "변동성 확대"
  - "불확실성 증가"
  unless absolutely necessary

- Write like a "핵심 해석" (insight), not a generic comment

Use category-based reasoning:

Company news:
- re-rating
- growth expectations
- business model shift
- competitive positioning

Macro news:
- rate path expectation
- liquidity / tightening / easing
- risk sentiment shift

Geopolitical / breaking:
- oil sensitivity
- safe-haven demand
- short-term risk-off

AI / tech:
- narrative strength
- demand expectations
- sector momentum

- Prefer styles like:
  - "재평가 가능성"
  - "기대감 재점화"
  - "성장 스토리 강화"
  - "금리 민감도 확대"

- Do NOT repeat recent implication styles

- If the market implication is weak, obvious, repetitive, or not clearly connected, leave implication empty.
- Prefer specific interpretation over generic sentiment language.
- Do not force implication for every accepted post.
- If no strong insight 👉 implication = ""

---

### Engagement rules:

- Optional, 1 short Korean line only
- Use only when meaningful discussion possible
- Avoid repetitive patterns
- Prefer empty for routine news

---

### Format rules:

- news_implication (default)
- news_implication_question (when discussion value exists)
- news_only (low-impact)
- news_implication_repost (rare, only for major breaking)

---

### Hashtag rules:

- 0-2 tags only
- "#태그1 #태그2"

Priority:
1. specific topic tag
2. one base tag if needed:
   - macro: #Fed #금리 #인플레이션
   - company: company name
   - market: #코스피 #코스닥 #증시

- Avoid generic tags
- Can be "" if not needed

---

Recent implication examples to avoid repeating:
{recent_implications}

Recent engagement examples to avoid repeating:
{recent_engagements}

Username: @{username}
Source tweet:
\"\"\"{tweet_text}\"\"\"

Recent posts:
{recent_posts}
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
            hashtags = _normalize_hashtags(str(data.get("hashtags", "")).strip(), limit=2)
            if format_type not in {
                "news_only",
                "news_implication",
                "news_implication_question",
                "news_implication_repost",
            }:
                format_type = "news_implication"

            # Implication must start with the configured marker when present.
            if implication:
                cleaned_implication = implication.lstrip("- ").strip()
                if cleaned_implication.startswith("→"):
                    cleaned_implication = cleaned_implication[1:].strip()
                if cleaned_implication.startswith("👉"):
                    implication = f"👉 {cleaned_implication[1:].strip()}".strip()
                else:
                    implication = f"👉 {cleaned_implication}".strip()

            # Guardrails: if skipped/irrelevant/similar, force no engagement payload.
            is_relevant = bool(data.get("is_relevant", False))
            is_similar = bool(data.get("is_similar", False))
            if (not is_relevant) or is_similar:
                summary = ""
                implication = ""
                engagement = ""
                hashtags = ""
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
                "hashtags": hashtags,
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
        "hashtags": "",
        "skip_reason": "ai_error",
        "error": str(last_error) if last_error else "unknown",
    }
