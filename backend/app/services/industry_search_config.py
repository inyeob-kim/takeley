"""Industry search words. DB rows override industries.py; an empty table does not."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import IndustrySearchConfig, XIngestConfig
from app.pipeline.industries import (
    DEFAULT_INDUSTRY_X_QUERIES,
    INDUSTRY_LABELS,
    ISSUE_INDUSTRY_KEYS,
    TopicLane,
)

_FREQUENCIES = {"every_scan", "every_2", "every_3"}
_PRIORITIES = {"high", "normal", "low"}
_MAX_KEYWORDS = 12
_OPERATOR = re.compile(r"(\bOR\b|\bAND\b|lang:|-is:|[()])", re.I)
_OR_SPLIT = re.compile(r"\s+OR\s+", re.I)

# Issue-producing industries stay every scan. Tail industries stay on, less often.
_DEFAULT_SCHEDULE: dict[str, tuple[str, str]] = {
    "politics": ("high", "every_scan"),
    "economy": ("high", "every_scan"),
    "ai": ("high", "every_scan"),
    "finance": ("normal", "every_2"),
    "tech": ("normal", "every_2"),
    "society": ("normal", "every_2"),
    "world": ("normal", "every_2"),
    "culture": ("low", "every_3"),
    "sports": ("low", "every_3"),
    "entertainment": ("low", "every_3"),
}


@dataclass(frozen=True)
class IndustryPlan:
    key: str
    label: str
    enabled: bool
    priority: str
    frequency: str
    query_ko: str
    query_en: str
    max_results: int | None


def keywords_from_stored_query(query: str) -> list[str]:
    match = re.search(r"\((.*)\)", query or "")
    body = match.group(1) if match else (query or "")
    words: list[str] = []
    for part in _OR_SPLIT.split(body):
        word = part.strip().strip('"').strip()
        if word and word not in words:
            words.append(word)
    return words


def parse_keyword_list(raw: str) -> list[str]:
    seen: list[str] = []
    known: set[str] = set()
    for part in re.split(r"[\n,]", str(raw or "")):
        word = part.strip().strip('"').strip()
        if not word:
            continue
        if _OPERATOR.search(word):
            raise ValueError("keywords cannot include search operators")
        if len(word) > 40:
            raise ValueError("keyword is too long")
        key = word.lower()
        if key in known:
            continue
        if len(seen) >= _MAX_KEYWORDS:
            raise ValueError("at most 12 keywords")
        seen.append(word)
        known.add(key)
    return seen


def _term(word: str) -> str:
    if re.search(r"[^\w]", word, re.UNICODE):
        return f'"{word}"'
    return word


def build_discovery_query(
    keywords: list[str],
    excludes: list[str],
    source_lane: str,
) -> str:
    if not keywords:
        return ""
    lang = "lang:ko" if source_lane == "korea" else "lang:en"
    body = " OR ".join(_term(word) for word in keywords)
    dropped = " ".join(f"-{_term(word)}" for word in excludes)
    query = f"({body}) {lang} -is:retweet"
    if dropped:
        query = f"{query} {dropped}"
    return query


def query_hash(query: str) -> str:
    return hashlib.sha1(query.encode("utf-8")).hexdigest()[:10]


def topic_query_cursor_key(industry_key: str, source_lane: str, query: str) -> str:
    return f"topic:{industry_key}:{source_lane}:{query_hash(query)}:since_id"


def fallback_plans(enabled_keys: tuple[str, ...] | None = None) -> list[IndustryPlan]:
    allowed = set(enabled_keys) if enabled_keys else set(ISSUE_INDUSTRY_KEYS)
    plans: list[IndustryPlan] = []
    for key in ISSUE_INDUSTRY_KEYS:
        lane_map = DEFAULT_INDUSTRY_X_QUERIES.get(key) or {}
        ko = keywords_from_stored_query(lane_map.get("korea") or "")
        en = keywords_from_stored_query(lane_map.get("global") or "")
        priority, frequency = _DEFAULT_SCHEDULE.get(key, ("normal", "every_2"))
        plans.append(
            IndustryPlan(
                key=key,
                label=INDUSTRY_LABELS.get(key, key),
                enabled=key in allowed,
                priority=priority,
                frequency=frequency,
                query_ko=build_discovery_query(ko, [], "korea"),
                query_en=build_discovery_query(en, [], "global"),
                max_results=None,
            )
        )
    return plans


def _plan_from_row(row: IndustrySearchConfig) -> IndustryPlan:
    ko = parse_keyword_list(row.keywords_ko)
    en = parse_keyword_list(row.keywords_en)
    ex_ko = parse_keyword_list(row.exclude_ko)
    ex_en = parse_keyword_list(row.exclude_en)
    return IndustryPlan(
        key=row.industry_key,
        label=INDUSTRY_LABELS.get(row.industry_key, row.industry_key),
        enabled=bool(row.enabled),
        priority=row.priority if row.priority in _PRIORITIES else "normal",
        frequency=row.frequency if row.frequency in _FREQUENCIES else "every_scan",
        query_ko=build_discovery_query(ko, ex_ko, "korea"),
        query_en=build_discovery_query(en, ex_en, "global"),
        max_results=row.max_results,
    )


def load_plans(db: Session) -> list[IndustryPlan] | None:
    """None means the table is empty and industries.py is still the source."""
    rows = (
        db.query(IndustrySearchConfig)
        .order_by(IndustrySearchConfig.industry_key)
        .all()
    )
    if not rows:
        return None
    by_key = {row.industry_key: row for row in rows}
    return [_plan_from_row(by_key[key]) for key in ISSUE_INDUSTRY_KEYS if key in by_key]


def ensure_seeded(db: Session) -> list[IndustrySearchConfig]:
    existing = db.query(IndustrySearchConfig).count()
    if existing:
        return (
            db.query(IndustrySearchConfig)
            .order_by(IndustrySearchConfig.industry_key)
            .all()
        )
    config = db.get(XIngestConfig, "default")
    enabled = set()
    if config and config.industries:
        enabled = {part.strip() for part in config.industries.split(",") if part.strip()}
    if not enabled:
        enabled = set(ISSUE_INDUSTRY_KEYS)
    for key in ISSUE_INDUSTRY_KEYS:
        lane_map = DEFAULT_INDUSTRY_X_QUERIES.get(key) or {}
        priority, frequency = _DEFAULT_SCHEDULE.get(key, ("normal", "every_2"))
        db.add(
            IndustrySearchConfig(
                industry_key=key,
                enabled=key in enabled,
                keywords_ko="\n".join(
                    keywords_from_stored_query(lane_map.get("korea") or "")
                ),
                keywords_en="\n".join(
                    keywords_from_stored_query(lane_map.get("global") or "")
                ),
                exclude_ko="",
                exclude_en="",
                priority=priority,
                frequency=frequency,
                max_results=None,
            )
        )
    db.commit()
    return (
        db.query(IndustrySearchConfig)
        .order_by(IndustrySearchConfig.industry_key)
        .all()
    )


def update_industries(db: Session, items: list[dict]) -> list[IndustrySearchConfig]:
    ensure_seeded(db)
    by_key = {
        row.industry_key: row for row in db.query(IndustrySearchConfig).all()
    }
    for item in items:
        key = str(item.get("industry_key") or "").strip().lower()
        row = by_key.get(key)
        if row is None:
            raise ValueError("unknown industry")
        if "enabled" in item:
            row.enabled = bool(item["enabled"])
        if "keywords_ko" in item:
            row.keywords_ko = "\n".join(parse_keyword_list(item["keywords_ko"]))
        if "keywords_en" in item:
            row.keywords_en = "\n".join(parse_keyword_list(item["keywords_en"]))
        if "exclude_ko" in item:
            row.exclude_ko = "\n".join(parse_keyword_list(item["exclude_ko"]))
        if "exclude_en" in item:
            row.exclude_en = "\n".join(parse_keyword_list(item["exclude_en"]))
        if "priority" in item:
            priority = str(item["priority"] or "")
            if priority not in _PRIORITIES:
                raise ValueError("priority must be high, normal, or low")
            row.priority = priority
        if "frequency" in item:
            frequency = str(item["frequency"] or "")
            if frequency not in _FREQUENCIES:
                raise ValueError("frequency must be every_scan, every_2, or every_3")
            row.frequency = frequency
        if "max_results" in item and item["max_results"] not in (None, ""):
            value = int(item["max_results"])
            if value < 10 or value > 100:
                raise ValueError("max results must be between 10 and 100")
            row.max_results = value
        elif "max_results" in item:
            row.max_results = None
    config = db.get(XIngestConfig, "default")
    if config is not None:
        enabled = [
            key
            for key in ISSUE_INDUSTRY_KEYS
            if key in by_key and by_key[key].enabled
        ]
        if enabled:
            config.industries = ",".join(enabled)
    db.commit()
    return (
        db.query(IndustrySearchConfig)
        .order_by(IndustrySearchConfig.industry_key)
        .all()
    )


def to_public(row: IndustrySearchConfig) -> dict:
    return {
        "industry_key": row.industry_key,
        "label": INDUSTRY_LABELS.get(row.industry_key, row.industry_key),
        "enabled": bool(row.enabled),
        "keywords_ko": row.keywords_ko or "",
        "keywords_en": row.keywords_en or "",
        "exclude_ko": row.exclude_ko or "",
        "exclude_en": row.exclude_en or "",
        "priority": row.priority,
        "frequency": row.frequency,
        "max_results": row.max_results,
    }


def frequency_due(frequency: str, scan_index: int) -> bool:
    if frequency == "every_2":
        return scan_index % 2 == 0
    if frequency == "every_3":
        return scan_index % 3 == 0
    return True


def select_rotation_lanes(
    plans: list[IndustryPlan],
    primary_lane: str,
    *,
    scan_index: int,
    limit: int,
    opposite_count: int,
) -> list[TopicLane]:
    """Primary language for industries due this scan, plus a few HIGH opposite lanes."""
    due = [
        plan
        for plan in plans
        if plan.enabled and frequency_due(plan.frequency, scan_index)
    ]
    primary = primary_lane if primary_lane in ("korea", "global") else "global"
    opposite = "global" if primary == "korea" else "korea"
    lanes: list[TopicLane] = []
    cap = max(1, limit)
    for plan in due:
        query = plan.query_ko if primary == "korea" else plan.query_en
        if not query:
            continue
        lanes.append(
            TopicLane(plan.key, primary, query, plan.max_results)
        )
        if len(lanes) >= cap:
            break
    added = 0
    for plan in due:
        if added >= max(0, opposite_count):
            break
        if plan.priority != "high":
            continue
        query = plan.query_en if opposite == "global" else plan.query_ko
        if not query:
            continue
        lanes.append(TopicLane(plan.key, opposite, query, plan.max_results))
        added += 1
    return lanes
