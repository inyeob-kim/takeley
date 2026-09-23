"""Locked Issue industries for trending topic ingest + category labels.

Region (korea|global) is a discovery lane only — never an Issue.category.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Canonical keys (lowercase) used in config, raw_payload, API filters.
ISSUE_INDUSTRY_KEYS: tuple[str, ...] = (
    "politics",
    "economy",
    "finance",
    "tech",
    "ai",
    "society",
    "world",
    "culture",
    "sports",
    "entertainment",
)

SOURCE_LANES: tuple[str, ...] = ("korea", "global")

# Display labels for UI / stored Signal.category (Korean; AI stays Latin).
INDUSTRY_LABELS: dict[str, str] = {
    "politics": "정치",
    "economy": "경제",
    "finance": "금융",
    "tech": "기술",
    "ai": "AI",
    "society": "사회",
    "world": "국제",
    "culture": "문화",
    "sports": "스포츠",
    "entertainment": "엔터",
}

# Legacy English labels (pre-KO rename) → canonical key.
_LEGACY_LABEL_TO_KEY: dict[str, str] = {
    "politics": "politics",
    "economy": "economy",
    "finance": "finance",
    "tech": "tech",
    "technology": "tech",
    "ai": "ai",
    "society": "society",
    "world": "world",
    "international": "world",
    "culture": "culture",
    "sports": "sports",
    "sport": "sports",
    "entertainment": "entertainment",
    "entertain": "entertainment",
}

# Volume-form queries (has:replies). Discovery strips has:replies.
# Global = prior lang:en queries. Korea = lang:ko (MVP; not "Korea-occurring events").
DEFAULT_INDUSTRY_X_QUERIES: dict[str, dict[str, str]] = {
    "politics": {
        "global": (
            '(Trump OR election OR Congress OR tariff OR "White House" OR geopolitics) '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(대통령 OR 국회 OR 정부 OR 여당 OR 야당 OR 선거 OR 총선 OR 대선 OR 정책) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "economy": {
        "global": (
            '(inflation OR recession OR CPI OR unemployment OR "cost of living") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(물가 OR 금리 OR 한국은행 OR 부동산 OR 집값 OR 전세 OR 고용 OR 실업 OR 수출 OR 환율) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "finance": {
        "global": (
            '(Fed OR FOMC OR "Wall Street" OR Nasdaq OR "interest rates") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(코스피 OR 코스닥 OR 증시 OR 주식 OR 금융 OR 은행 OR 증권 OR 채권 OR 원달러) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "tech": {
        "global": (
            '("Big Tech" OR Apple OR Google OR Nvidia OR semiconductor OR antitrust) '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(반도체 OR 플랫폼 OR 테크 OR 삼성전자 OR SK하이닉스 OR 애플 OR 구글 OR 기술규제) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "ai": {
        "global": (
            '(AI OR ChatGPT OR OpenAI OR LLM OR "artificial intelligence") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(AI OR 인공지능 OR 생성형AI OR ChatGPT OR OpenAI OR LLM OR 생성형) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "society": {
        "global": (
            '(housing OR protest OR "social issue" OR inequality OR "gun violence" OR immigration) '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(주거 OR 교육 OR 저출산 OR 노동 OR 이민 OR 시위 OR 사회문제 OR 복지) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "world": {
        "global": (
            '(Ukraine OR Gaza OR "Middle East" OR NATO OR "trade war" OR summit OR UN) '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(우크라이나 OR 가자 OR 중동 OR 미국 OR 중국 OR 일본 OR NATO OR 정상회담 OR 외교) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "culture": {
        "global": (
            '(museum OR "film festival" OR literature OR Broadway OR "cultural heritage") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(문화 OR 영화제 OR 미술 OR 문학 OR 공연 OR 전시 OR 뮤지컬 OR 콘서트) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "sports": {
        "global": (
            '(Olympics OR "World Cup" OR NBA OR NFL OR MLB OR "Premier League") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(축구 OR 야구 OR 농구 OR 올림픽 OR 월드컵 OR K리그 OR MLB OR NBA OR 스포츠) "
            "lang:ko -is:retweet has:replies"
        ),
    },
    "entertainment": {
        "global": (
            '(Netflix OR Hollywood OR "K-pop" OR Oscars OR Grammy OR "box office") '
            "lang:en -is:retweet has:replies"
        ),
        "korea": (
            "(넷플릭스 OR 영화 OR 드라마 OR K팝 OR 아이돌 OR 배우 OR 시상식 OR 예능) "
            "lang:ko -is:retweet has:replies"
        ),
    },
}


class TopicLane(NamedTuple):
    industry_key: str
    source_lane: str
    query: str
    max_results: int | None = None


def _strip_has_replies(query: str) -> str:
    return query.replace(" has:replies", "").replace("has:replies", "").strip()


def discovery_query_for(
    industry_key: str, source_lane: str = "global"
) -> str | None:
    """Broad discovery query without mandatory has:replies."""
    lane_map = DEFAULT_INDUSTRY_X_QUERIES.get(industry_key)
    if not lane_map:
        return None
    base = lane_map.get(source_lane)
    if not base:
        return None
    return _strip_has_replies(base)


def volume_query_for(
    industry_key: str, source_lane: str = "global"
) -> str | None:
    """Engagement lane query (keeps has:replies when present)."""
    lane_map = DEFAULT_INDUSTRY_X_QUERIES.get(industry_key)
    if not lane_map:
        return None
    return lane_map.get(source_lane)


def build_topic_lanes(enabled_keys: tuple[str, ...]) -> list[TopicLane]:
    """Flatten enabled industries × korea/global into discovery lanes.

    Order: for each industry in enabled_keys, korea then global.
    MVP uses discovery only (no has:replies).
    """
    lanes: list[TopicLane] = []
    for key in enabled_keys:
        if key not in ISSUE_INDUSTRY_KEYS:
            continue
        for source_lane in SOURCE_LANES:
            q = discovery_query_for(key, source_lane)
            if q:
                lanes.append(TopicLane(key, source_lane, q))
    return lanes


def select_topic_lanes(
    lanes: list[TopicLane],
    budget: int,
    offset: int,
    stats: Any | None = None,
) -> tuple[list[TopicLane], int]:
    """Pick up to ``budget`` lanes via deterministic round-robin.

    ``stats`` is reserved for a future adaptive scheduler; unused in MVP.
    """
    _ = stats
    if not lanes:
        return [], 0
    n = len(lanes)
    budget = max(1, min(int(budget), n))
    start = int(offset) % n
    selected = [lanes[(start + i) % n] for i in range(budget)]
    next_offset = (start + budget) % n
    return selected, next_offset


def topic_since_cursor_key(industry_key: str, source_lane: str) -> str:
    return f"topic:{industry_key}:{source_lane}:since_id"


def legacy_topic_since_cursor_key(industry_key: str) -> str:
    """Pre-lane cursor key (kept for seed; never deleted)."""
    return f"topic:{industry_key}:since_id"


def _build_label_to_key() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for key, label in INDUSTRY_LABELS.items():
        mapping[key] = key
        mapping[label.lower()] = key
    mapping.update(_LEGACY_LABEL_TO_KEY)
    return mapping


_LABEL_TO_KEY = _build_label_to_key()

# All strings that may appear in Signal.category for a given key (filter OR).
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    key: tuple(
        sorted(
            {
                INDUSTRY_LABELS[key],
                key,
                key.title() if key != "ai" else "AI",
                *(
                    legacy.title() if legacy != "ai" else "AI"
                    for legacy, k in _LEGACY_LABEL_TO_KEY.items()
                    if k == key
                ),
            }
        )
    )
    for key in ISSUE_INDUSTRY_KEYS
}
# Fix AI aliases explicitly.
CATEGORY_ALIASES["ai"] = ("AI", "ai", "Ai")
CATEGORY_ALIASES["tech"] = ("기술", "Tech", "tech", "Technology")
CATEGORY_ALIASES["politics"] = ("정치", "Politics", "politics")
CATEGORY_ALIASES["economy"] = ("경제", "Economy", "economy")
CATEGORY_ALIASES["finance"] = ("금융", "Finance", "finance")
CATEGORY_ALIASES["society"] = ("사회", "Society", "society")
CATEGORY_ALIASES["world"] = ("국제", "World", "world", "International")
CATEGORY_ALIASES["culture"] = ("문화", "Culture", "culture")
CATEGORY_ALIASES["sports"] = ("스포츠", "Sports", "sports", "Sport")
CATEGORY_ALIASES["entertainment"] = ("엔터", "Entertainment", "entertainment")


def parse_industry_keys(raw: str | None) -> tuple[str, ...]:
    if not (raw or "").strip():
        return ISSUE_INDUSTRY_KEYS
    out: list[str] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if key in ISSUE_INDUSTRY_KEYS and key not in out:
            out.append(key)
    return tuple(out) if out else ISSUE_INDUSTRY_KEYS


def normalize_industry_category(raw: str | None) -> str | None:
    """Map LLM / stored / query category to locked industry label, or None."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    key = _LABEL_TO_KEY.get(text.lower())
    if key:
        return INDUSTRY_LABELS[key]
    lowered = text.lower()
    for k, label in INDUSTRY_LABELS.items():
        if k in lowered or label.lower() in lowered:
            return label
    return None


def category_filter_values(raw: str | None) -> list[str] | None:
    """DB values to match for a category query (includes legacy English)."""
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    key = _LABEL_TO_KEY.get(text.lower())
    if not key:
        label = normalize_industry_category(text)
        if not label:
            return None
        key = _LABEL_TO_KEY.get(label.lower())
    if not key:
        return None
    return list(CATEGORY_ALIASES.get(key, (INDUSTRY_LABELS[key],)))


def industry_x_queries(
    enabled_keys: tuple[str, ...],
    *,
    split_replies: bool = False,
    source_lane: str = "global",
) -> list[tuple[str, str]]:
    """Return (industry_key, query) for one lane (compat helper).

    Prefer ``build_topic_lanes`` for ingest. ``split_replies=True`` → discovery.
    """
    pairs: list[tuple[str, str]] = []
    lane = source_lane if source_lane in SOURCE_LANES else "global"
    for key in enabled_keys:
        if split_replies:
            q = discovery_query_for(key, lane)
        else:
            q = volume_query_for(key, lane)
        if q:
            pairs.append((key, q))
    return pairs


def all_industry_labels() -> list[str]:
    """Canonical labels plus legacy English (for feed inclusion)."""
    labels = list(INDUSTRY_LABELS.values())
    for aliases in CATEGORY_ALIASES.values():
        for a in aliases:
            if a not in labels:
                labels.append(a)
    return labels
