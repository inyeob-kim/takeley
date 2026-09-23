"""Dynamic X search queries derived from recent Understanding topics (Phase B light)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from app.db.repositories import CursorRepository

logger = logging.getLogger(__name__)

_CURSOR_PROVIDER = "x"
_CURSOR_KEY = "dynamic:topics"
_ROWS_KEY = "dynamic:rows"
_MAX_TOPICS = 12
_DEFAULT_MAX_ACTIVE = 4
_DEFAULT_TTL_HOURS = 12
_DEFAULT_IDLE_LIMIT = 2


def _sanitize_topic(topic: str) -> str | None:
    t = re.sub(r"[^\w\s\-\.]", " ", (topic or "").strip())
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < 4:
        return None
    # X query: quote multi-word
    parts = t.split()[:6]
    if len(parts) == 1:
        return f"{parts[0]} lang:en -is:retweet"
    return f"\"{' '.join(parts)}\" lang:en -is:retweet"


def remember_topics(cursor_repo: CursorRepository, topics: list[str]) -> None:
    existing_raw = cursor_repo.get(_CURSOR_PROVIDER, _CURSOR_KEY) or ""
    existing = [p for p in existing_raw.split("|") if p.strip()]
    for topic in topics:
        clean = (topic or "").strip()[:80]
        if not clean:
            continue
        if clean not in existing:
            existing.insert(0, clean)
    existing = existing[:_MAX_TOPICS]
    cursor_repo.set(_CURSOR_PROVIDER, _CURSOR_KEY, "|".join(existing))


def dynamic_search_queries(
    cursor_repo: CursorRepository, *, budget: int = 2
) -> list[str]:
    """Build up to `budget` recent-search queries from remembered topics."""
    raw = cursor_repo.get(_CURSOR_PROVIDER, _CURSOR_KEY) or ""
    topics = [p for p in raw.split("|") if p.strip()]
    out: list[str] = []
    for topic in topics:
        q = _sanitize_topic(topic)
        if q and q not in out:
            out.append(q)
        if len(out) >= max(0, budget):
            break
    return out


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def _topic_key(topic: str) -> str:
    return hashlib.sha1(topic.strip().lower().encode("utf-8")).hexdigest()[:10]


def _load_rows(cursor_repo: CursorRepository) -> list[dict]:
    raw = cursor_repo.get(_CURSOR_PROVIDER, _ROWS_KEY) or ""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _save_rows(cursor_repo: CursorRepository, rows: list[dict]) -> None:
    cursor_repo.set(_CURSOR_PROVIDER, _ROWS_KEY, json.dumps(rows, ensure_ascii=False))


def _query_for(topic: str, source_lane: str) -> str | None:
    base = _sanitize_topic(topic)
    if not base:
        return None
    lang = "lang:ko" if source_lane == "korea" else "lang:en"
    return base.replace("lang:en", lang)


def arm_dynamic_topic(
    cursor_repo: CursorRepository,
    *,
    topic: str,
    industry: str,
    source_lane: str,
    now: datetime | None = None,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
    max_active: int = _DEFAULT_MAX_ACTIVE,
) -> bool:
    """One temporary follow-up query. Duplicates and a full list are ignored."""
    clean = (topic or "").strip()[:80]
    query = _query_for(clean, source_lane if source_lane in ("korea", "global") else "global")
    if not query:
        return False
    current = _now(now)
    rows = []
    for row in _load_rows(cursor_repo):
        until = _parse_iso(row.get("until"))
        cool = _parse_iso(row.get("cool_until"))
        if cool and cool > current:
            rows.append(row)
            continue
        if until and until <= current:
            continue
        if int(row.get("idle") or 0) >= _DEFAULT_IDLE_LIMIT:
            continue
        rows.append(row)
    if any(str(row.get("topic") or "").lower() == clean.lower() for row in rows):
        _save_rows(cursor_repo, rows)
        return False
    active = [row for row in rows if not row.get("cool_until")]
    if len(active) >= max(1, max_active):
        _save_rows(cursor_repo, rows)
        return False
    lane = source_lane if source_lane in ("korea", "global") else "global"
    rows.append(
        {
            "key": _topic_key(clean),
            "topic": clean,
            "query": query,
            "industry": industry or "dynamic",
            "source_lane": lane,
            "since_id": None,
            "idle": 0,
            "scans": 0,
            "until": (current + timedelta(hours=max(1, ttl_hours))).isoformat(),
            "cool_until": None,
        }
    )
    _save_rows(cursor_repo, rows)
    return True


def active_dynamic_queries(
    cursor_repo: CursorRepository,
    *,
    now: datetime | None = None,
    limit: int = _DEFAULT_MAX_ACTIVE,
) -> list[dict]:
    current = _now(now)
    kept = []
    live = []
    for row in _load_rows(cursor_repo):
        until = _parse_iso(row.get("until"))
        cool = _parse_iso(row.get("cool_until"))
        if cool and cool > current:
            kept.append(row)
            continue
        if cool and cool <= current:
            continue
        if until and until <= current:
            continue
        if int(row.get("idle") or 0) >= _DEFAULT_IDLE_LIMIT:
            continue
        kept.append(row)
        live.append(row)
    _save_rows(cursor_repo, kept)
    return live[: max(0, limit)]


def mark_dynamic_polled(
    cursor_repo: CursorRepository,
    *,
    key: str,
    since_id: str | None,
) -> None:
    rows = _load_rows(cursor_repo)
    for row in rows:
        if row.get("key") != key:
            continue
        row["polled"] = True
        row["scans"] = int(row.get("scans") or 0) + 1
        if since_id:
            row["since_id"] = since_id
    _save_rows(cursor_repo, rows)


def settle_dynamic_polls(
    cursor_repo: CursorRepository,
    *,
    meaningful: set[str],
    idle_limit: int = _DEFAULT_IDLE_LIMIT,
    cooldown_hours: int = 6,
    now: datetime | None = None,
) -> None:
    """End a follow-up when this scan added no Issue and no evidence."""
    current = _now(now)
    rows = []
    for row in _load_rows(cursor_repo):
        if not row.get("polled"):
            rows.append(row)
            continue
        row["polled"] = False
        lane_key = f"{row.get('industry')}:{row.get('source_lane')}"
        row["idle"] = 0 if lane_key in meaningful else int(row.get("idle") or 0) + 1
        if row["idle"] >= idle_limit:
            row["cool_until"] = (
                current + timedelta(hours=max(1, cooldown_hours))
            ).isoformat()
            row["until"] = current.isoformat()
        rows.append(row)
    _save_rows(cursor_repo, rows)


def note_dynamic_result(
    cursor_repo: CursorRepository,
    *,
    key: str,
    since_id: str | None,
    meaningful: bool,
    idle_limit: int = _DEFAULT_IDLE_LIMIT,
    cooldown_hours: int = 6,
    now: datetime | None = None,
) -> None:
    current = _now(now)
    rows = []
    for row in _load_rows(cursor_repo):
        if row.get("key") != key:
            rows.append(row)
            continue
        row["scans"] = int(row.get("scans") or 0) + 1
        if since_id:
            row["since_id"] = since_id
        row["idle"] = 0 if meaningful else int(row.get("idle") or 0) + 1
        if row["idle"] >= idle_limit:
            row["cool_until"] = (
                current + timedelta(hours=max(1, cooldown_hours))
            ).isoformat()
            row["until"] = current.isoformat()
        rows.append(row)
    _save_rows(cursor_repo, rows)


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
