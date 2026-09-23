"""Admin-editable X ingest settings and cost rollups.

Dollar estimates use the rates stored on the config row. They are not a
second cost system — counts still come from usage_events.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import Issue, RawItem, UsageEvent, XIngestConfig
from app.pipeline.industries import INDUSTRY_LABELS, parse_industry_keys
from app.pipeline.x_schedule import HOT_PREFIX, LAST_SLOT_KEY, decode_hot

CONFIG_ID = "default"
_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
_MAX_TRACK_ACCOUNTS = 20

_LANES = {"korea", "global"}
_ACCOUNTS_ON = {"off", "morning", "night", "all"}
_DYNAMIC = {"off", "normal", "hot"}
_SCAN_MODES = {"scheduled", "interval"}


def get_or_create(db: Session) -> XIngestConfig:
    row = db.get(XIngestConfig, CONFIG_ID)
    if row is not None:
        return row
    row = XIngestConfig(id=CONFIG_ID)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _sync_industry_enabled(db: Session, industries: str) -> None:
    from app.db.models import IndustrySearchConfig

    rows = db.query(IndustrySearchConfig).all()
    if not rows:
        return
    enabled = {part.strip() for part in industries.split(",") if part.strip()}
    for item in rows:
        item.enabled = item.industry_key in enabled


def parse_track_accounts(raw) -> list[str]:
    """Comma-separated X handles. Empty is allowed. @ and duplicates are dropped."""
    seen: list[str] = []
    known = {item.lower() for item in seen}
    for part in str(raw or "").split(","):
        name = part.strip().lstrip("@")
        if not name:
            continue
        if not _HANDLE.match(name):
            raise ValueError(
                "account names are letters, numbers, and underscore, up to 15 characters"
            )
        if name.lower() in known:
            continue
        if len(seen) >= _MAX_TRACK_ACCOUNTS:
            raise ValueError("at most 20 accounts")
        seen.append(name)
        known.add(name.lower())
    return seen


def update_config(db: Session, payload: dict) -> XIngestConfig:
    row = get_or_create(db)
    if "scan_mode" in payload:
        mode = str(payload["scan_mode"] or "")
        if mode not in _SCAN_MODES:
            raise ValueError("scan_mode must be scheduled or interval")
        row.scan_mode = mode
    if "scan_hours_kst" in payload:
        row.scan_hours_kst = str(payload["scan_hours_kst"] or "").strip()[:128]
    if "scan_window_minutes" in payload:
        row.scan_window_minutes = _clamp(payload["scan_window_minutes"], 5, 180)
    if "morning_lane" in payload:
        row.morning_lane = _lane(payload["morning_lane"])
    if "afternoon_lane" in payload:
        row.afternoon_lane = _lane(payload["afternoon_lane"])
    if "night_lane" in payload:
        night = str(payload["night_lane"] or "")
        row.night_lane = "auto" if night == "auto" else _lane(night)
    if "lanes_per_scan" in payload:
        row.lanes_per_scan = _clamp(payload["lanes_per_scan"], 1, 20)
    if "max_results" in payload:
        row.max_results = _clamp(payload["max_results"], 10, 100)
    if "industries" in payload:
        keys = parse_industry_keys(str(payload["industries"] or ""))
        if not keys:
            raise ValueError("at least one industry is required")
        row.industries = ",".join(keys)
    if "track_accounts" in payload:
        row.track_accounts = ",".join(parse_track_accounts(payload["track_accounts"]))
    if "accounts_on" in payload:
        value = str(payload["accounts_on"] or "")
        if value not in _ACCOUNTS_ON:
            raise ValueError("accounts_on must be off, morning, night, or all")
        row.accounts_on = value
    if "dynamic_mode" in payload:
        value = str(payload["dynamic_mode"] or "")
        if value not in _DYNAMIC:
            raise ValueError("dynamic_mode must be off, normal, or hot")
        row.dynamic_mode = value
    if "hot_enabled" in payload:
        row.hot_enabled = bool(payload["hot_enabled"])
    if "hot_interval_minutes" in payload:
        row.hot_interval_minutes = _clamp(payload["hot_interval_minutes"], 15, 240)
    if "hot_idle_scans" in payload:
        row.hot_idle_scans = _clamp(payload["hot_idle_scans"], 1, 12)
    if "hot_max_hours" in payload:
        row.hot_max_hours = _clamp(payload["hot_max_hours"], 1, 48)
    if "hot_reply_spike" in payload:
        row.hot_reply_spike = _clamp(payload["hot_reply_spike"], 1, 500)
    if "understand_budget" in payload:
        row.understand_budget = _clamp(payload["understand_budget"], 1, 40)
    if "industry_slot_reserve" in payload:
        row.industry_slot_reserve = bool(payload["industry_slot_reserve"])
    if "usd_per_post" in payload:
        row.usd_per_post = _money(payload["usd_per_post"])
    if "usd_per_user" in payload:
        row.usd_per_user = _money(payload["usd_per_user"])
    if "opposite_lane_count" in payload:
        row.opposite_lane_count = _clamp(payload["opposite_lane_count"], 0, 10)
    if "daily_post_budget" in payload:
        row.daily_post_budget = _clamp(payload["daily_post_budget"], 0, 5000)
    if "industries" in payload:
        _sync_industry_enabled(db, row.industries)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def stats(db: Session, *, days: int = 7) -> dict:
    config = get_or_create(db)
    since = datetime.utcnow() - timedelta(days=max(1, days))
    posts = {key: 0 for key in parse_industry_keys(config.industries)}
    processed = {key: 0 for key in posts}
    lane_posts: dict[str, dict[str, int]] = {}
    korea_posts = 0
    global_posts = 0
    for raw_payload, flag, fetched_at in (
        db.query(RawItem.raw_payload, RawItem.processed, RawItem.fetched_at)
        .filter(RawItem.provider == "x", RawItem.fetched_at >= since)
        .all()
    ):
        industry = _industry_of(raw_payload)
        if industry not in posts:
            posts.setdefault(industry, 0)
            processed.setdefault(industry, 0)
        posts[industry] += 1
        lane = _lane_of(raw_payload)
        bucket = lane_posts.setdefault(industry, {"korea": 0, "global": 0})
        if lane == "korea":
            korea_posts += 1
            bucket["korea"] += 1
        elif lane == "global":
            global_posts += 1
            bucket["global"] += 1
        if flag:
            processed[industry] += 1

    issues = {key: 0 for key in posts}
    updates: dict[str, int] = {}
    label_to_key = {label: key for key, label in INDUSTRY_LABELS.items()}
    for category, created in (
        db.query(Issue.category, Issue.first_seen_at)
        .filter(Issue.first_seen_at >= since)
        .all()
    ):
        _ = created
        key = label_to_key.get(category or "") or (category or "").lower()
        if key in INDUSTRY_LABELS or key in issues:
            issues[key] = issues.get(key, 0) + 1

    calls = {key: 0 for key in posts}
    post_units = 0.0
    user_units = 0.0
    search_calls = 0.0
    timeline_calls = 0.0
    slot_posts: dict[str, float] = {}
    slot_issues: dict[str, float] = {}
    dynamic_queries = 0
    hot_scans = 0
    for metric, value, tags in (
        db.query(UsageEvent.metric, UsageEvent.value, UsageEvent.tags)
        .filter(
            UsageEvent.created_at >= since,
            UsageEvent.metric.in_(
                ("x_api_requests", "x_posts_received", "x_search_requests")
            ),
        )
        .all()
    ):
        tag = tags if isinstance(tags, dict) else {}
        industry = str(tag.get("industry") or "")
        if metric == "x_api_requests":
            endpoint = str(tag.get("endpoint") or "")
            if endpoint == "get_user":
                user_units += float(value or 0)
            elif endpoint == "get_users_tweets":
                timeline_calls += float(value or 0)
            else:
                search_calls += float(value or 0)
                if str(tag.get("query_kind") or "") == "dynamic":
                    dynamic_queries += int(value or 0)
                if str(tag.get("mode") or "") == "hot":
                    hot_scans += int(value or 0)
            if industry:
                calls[industry] = calls.get(industry, 0) + int(value or 0)
        elif metric == "x_posts_received":
            post_units += float(value or 0)
            slot = str(tag.get("scan_slot") or tag.get("mode") or "unscoped")
            slot_posts[slot] = slot_posts.get(slot, 0) + float(value or 0)
        elif metric == "x_search_requests":
            search_calls += 0

    for metric, value, tags in (
        db.query(UsageEvent.metric, UsageEvent.value, UsageEvent.tags)
        .filter(
            UsageEvent.created_at >= since,
            UsageEvent.metric.in_(("issue_created", "issue_updated")),
        )
        .all()
    ):
        tag = tags if isinstance(tags, dict) else {}
        slot = str(tag.get("scan_slot") or "unscoped")
        if metric == "issue_created":
            slot_issues[slot] = slot_issues.get(slot, 0) + float(value or 0)
        elif metric == "issue_updated":
            key = str(tag.get("industry") or "")
            if key:
                updates[key] = updates.get(key, 0) + int(value or 0)

    new_issues = sum(issues.values())
    update_count = sum(updates.values())
    estimated = post_units * float(config.usd_per_post) + user_units * float(
        config.usd_per_user
    )
    per_issue = (estimated / new_issues) if new_issues else None
    industries = []
    for key in list(posts.keys()):
        issue_count = issues.get(key, 0)
        usd = round(posts.get(key, 0) * float(config.usd_per_post), 4)
        split = lane_posts.get(key) or {"korea": 0, "global": 0}
        industries.append(
            {
                "industry": key,
                "label": INDUSTRY_LABELS.get(key, key),
                "posts": posts.get(key, 0),
                "korea_posts": split["korea"],
                "global_posts": split["global"],
                "processed": processed.get(key, 0),
                "issues": issue_count,
                "updates": updates.get(key, 0),
                "api_calls": calls.get(key, 0),
                "estimated_usd": usd,
                "usd_per_issue": round(usd / issue_count, 4) if issue_count else None,
            }
        )
    return {
        "days": days,
        "posts_fetched": int(post_units) if post_units else sum(posts.values()),
        "search_calls": int(search_calls),
        "timeline_calls": int(timeline_calls),
        "user_lookups": int(user_units),
        "new_issues": new_issues,
        "updates": update_count,
        "estimated_usd": round(estimated, 4),
        "usd_per_new_issue": None if per_issue is None else round(per_issue, 4),
        "korea_posts": korea_posts,
        "global_posts": global_posts,
        "dynamic_queries": dynamic_queries,
        "hot_scans": hot_scans,
        "slots": _slot_rows(slot_posts, slot_issues, float(config.usd_per_post)),
        "industries": industries,
        "hot": _hot_rows(db),
        "last_slot_key": _last_slot_key(db),
    }


def _slot_rows(
    posts: dict[str, float],
    issues: dict[str, float],
    usd_per_post: float,
) -> list[dict]:
    names = sorted(set(posts) | set(issues))
    rows = []
    for name in names:
        post_count = int(posts.get(name, 0))
        issue_count = int(issues.get(name, 0))
        usd = round(post_count * usd_per_post, 4)
        rows.append(
            {
                "slot": name,
                "posts": post_count,
                "issues": issue_count,
                "estimated_usd": usd,
                "usd_per_issue": round(usd / issue_count, 4) if issue_count else None,
            }
        )
    return rows


def _last_slot_key(db: Session) -> str | None:
    from app.db.repositories import CursorRepository

    return CursorRepository(db).get("x", LAST_SLOT_KEY)


def _hot_rows(db: Session) -> list[dict]:
    from app.db.models import IngestCursor

    rows = (
        db.query(IngestCursor)
        .filter(
            IngestCursor.provider == "x",
            IngestCursor.cursor_key.like(f"{HOT_PREFIX}%"),
        )
        .all()
    )
    out = []
    for row in rows:
        parsed = decode_hot(row.cursor_value)
        body = row.cursor_key[len(HOT_PREFIX) :]
        industry, _, lane = body.partition(":")
        out.append(
            {
                "industry": industry,
                "lane": lane,
                "idle": parsed[1] if parsed else 0,
                "until": parsed[2].isoformat() if parsed else None,
            }
        )
    return out


def _lane_of(payload) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("source_lane") or "")


def _industry_of(payload) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return "other"
    if not isinstance(payload, dict):
        return "other"
    return str(payload.get("issue_industry") or "other")


def _lane(value) -> str:
    text = str(value or "")
    if text not in _LANES:
        raise ValueError("lane must be korea or global")
    return text


def _clamp(value, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected an integer") from exc
    return max(low, min(high, number))


def _money(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("expected a number") from exc
    if number < 0 or number > 1:
        raise ValueError("rate must be between 0 and 1")
    return number
