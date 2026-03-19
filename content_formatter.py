import re
from typing import List, Tuple


OPENING_PREFIXES = ("⚡ 속보", "📈 시장 속보", "🚨 긴급")
TARGET_FORMAT_RATIOS = {
    "news_implication": 0.40,
    "news_implication_question": 0.35,
    "news_only": 0.15,
    "news_implication_repost": 0.10,
}


def _clean_line(text: str) -> str:
    return " ".join((text or "").strip().split())


def _clean_summary(text: str) -> str:
    lines = [" ".join(line.strip().split()) for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines).strip()


def _clean_hashtags(text: str, limit: int = 2) -> str:
    tokens = []
    seen = set()
    for token in (text or "").split():
        if not token.startswith("#"):
            continue
        cleaned_body = re.sub(r"[^0-9A-Za-z가-힣_]", "", token[1:])
        if not cleaned_body:
            continue
        normalized = f"#{cleaned_body}"
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        tokens.append(normalized)
        if len(tokens) >= limit:
            break
    return " ".join(tokens)


def _remove_at_mentions(text: str) -> str:
    """
    Remove @-mention syntax to comply with policy restrictions on unsolicited mentions.
    """
    return re.sub(r"(^|\s)@([A-Za-z0-9_]{1,15})", r"\1\2", text or "")


def _select_opening(summary: str, recent_prefixes: List[str]) -> str:
    text = (summary or "").strip()
    for prefix in OPENING_PREFIXES:
        if text.startswith(prefix):
            return text

    # Anti-repetition: prefer a header that was used least in recent posts.
    counts = {prefix: recent_prefixes.count(prefix) for prefix in OPENING_PREFIXES}
    selected = min(OPENING_PREFIXES, key=lambda prefix: counts[prefix])
    return f"{selected}\n\n{text}" if text else selected


def assemble_final_post_text(
    *,
    format_type: str,
    summary: str,
    implication: str,
    engagement: str,
    hashtags: str,
    tweet_url: str,
    recent_prefixes: List[str] | None = None,
) -> Tuple[str, str]:
    """
    Build final post text with strict line ordering.
    Returns:
    - final_text: assembled tweet text
    - normalized_format_type: final format used after field normalization
    """
    recent_prefixes = recent_prefixes or []
    normalized_type = (format_type or "news_implication").strip().lower()
    if normalized_type not in {
        "news_only",
        "news_implication",
        "news_implication_question",
        "news_implication_repost",
    }:
        normalized_type = "news_implication"

    summary_line = _select_opening(_clean_summary(summary), recent_prefixes)
    implication_line = _clean_line(implication)
    engagement_line = _clean_line(engagement)
    hashtag_line = _clean_hashtags(hashtags, limit=2)

    if implication_line and not implication_line.startswith("→"):
        implication_line = f"→ {implication_line.lstrip('- ').strip()}"

    # Normalize malformed AI output while preserving stable posting behavior.
    if normalized_type == "news_only":
        implication_line = ""
        engagement_line = ""
    elif normalized_type == "news_implication":
        if not implication_line:
            normalized_type = "news_only"
        engagement_line = ""
    elif normalized_type in {"news_implication_question", "news_implication_repost"}:
        if not implication_line:
            normalized_type = "news_only"
            engagement_line = ""
        elif not engagement_line:
            normalized_type = "news_implication"

    lines = [summary_line]
    if normalized_type != "news_only" and implication_line:
        lines.extend(["", implication_line])
    if normalized_type in {"news_implication_question", "news_implication_repost"} and engagement_line:
        lines.extend(["", engagement_line])
    if hashtag_line:
        lines.extend(["", hashtag_line])

    if tweet_url:
        lines.extend(["", tweet_url.strip()])
    final_text = _remove_at_mentions("\n".join(lines).strip())
    return final_text, normalized_type


def is_repetitive_line(line: str, recent_lines: List[str], max_recent_reuse: int = 1) -> bool:
    clean_line = _clean_line(line)
    if not clean_line:
        return False
    clean_recent = [_clean_line(item) for item in recent_lines if _clean_line(item)]
    return clean_recent.count(clean_line) > max_recent_reuse


def rebalance_format_type(
    *,
    suggested_format_type: str,
    news_type: str,
    has_implication: bool,
    has_engagement: bool,
    recent_format_types: List[str],
) -> str:
    """
    Soft-balances format mix while keeping AI intent whenever possible.
    """
    normalized = (suggested_format_type or "news_implication").strip().lower()
    if normalized not in TARGET_FORMAT_RATIOS:
        normalized = "news_implication"

    allowed = {"news_only"}
    if has_implication:
        allowed.add("news_implication")
    if has_implication and has_engagement:
        allowed.add("news_implication_question")
        if (news_type or "").strip().lower() in {"macro", "breaking"}:
            allowed.add("news_implication_repost")

    if normalized not in allowed:
        if "news_implication" in allowed:
            normalized = "news_implication"
        else:
            normalized = "news_only"

    history = [item for item in recent_format_types if item in TARGET_FORMAT_RATIOS]
    if len(history) < 10:
        return normalized

    current_ratios = {
        key: history.count(key) / len(history) for key in TARGET_FORMAT_RATIOS
    }
    deficits = {
        key: TARGET_FORMAT_RATIOS[key] - current_ratios.get(key, 0.0) for key in TARGET_FORMAT_RATIOS
    }

    if deficits.get(normalized, 0.0) > -0.12:
        return normalized

    allowed_sorted = sorted(allowed, key=lambda key: deficits.get(key, -1.0), reverse=True)
    return allowed_sorted[0] if allowed_sorted else normalized

