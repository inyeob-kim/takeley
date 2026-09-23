"""Wall-clock X scan slots and hot-topic cursors.

Hot state is an ingest cursor, not an Issue trend_status.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.pipeline.industries import TopicLane, build_topic_lanes

KST = ZoneInfo("Asia/Seoul")
LAST_SLOT_KEY = "schedule:last_slot"
SCAN_INDEX_KEY = "schedule:scan_index"
POSTS_DAY_KEY = "schedule:posts_kst"
HOT_PREFIX = "hot:"


@dataclass(frozen=True)
class ScanSlot:
    index: int
    label: str
    hour: int
    minute: int
    key: str


def parse_scan_hours(raw: str) -> list[tuple[int, int]]:
    hours: list[tuple[int, int]] = []
    for part in (raw or "").split(","):
        text = part.strip()
        if not text or ":" not in text:
            continue
        hh, mm = text.split(":", 1)
        if not hh.isdigit() or not mm.isdigit():
            continue
        hour = int(hh)
        minute = int(mm)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            hours.append((hour, minute))
    return hours


def slot_label(index: int) -> str:
    return ("morning", "afternoon", "night")[index] if index < 3 else f"slot{index}"


def due_slot(
    now_utc: datetime,
    hours_raw: str,
    *,
    window_minutes: int,
    last_slot_key: str | None,
) -> ScanSlot | None:
    """Return the slot whose window contains now, if it has not fired yet."""
    hours = parse_scan_hours(hours_raw)
    if not hours:
        return None
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    local = now.astimezone(KST)
    window = timedelta(minutes=max(1, window_minutes))
    for index, (hour, minute) in enumerate(hours):
        start = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if local < start or local >= start + window:
            continue
        key = start.strftime("%Y-%m-%dT%H:%M")
        if last_slot_key == key:
            return None
        return ScanSlot(
            index=index,
            label=slot_label(index),
            hour=hour,
            minute=minute,
            key=key,
        )
    return None


def weaker_source_lane(
    korea_count: int,
    global_count: int,
    *,
    afternoon: str,
) -> str:
    """Night scan covers the lane with fewer analyzed posts today.

    A tie takes the lane the afternoon scan did not use, so one language
    does not get all three passes.
    """
    if korea_count < global_count:
        return "korea"
    if global_count < korea_count:
        return "global"
    return "korea" if afternoon == "global" else "global"


def lane_for_slot(
    index: int,
    morning: str,
    afternoon: str,
    night: str,
    *,
    korea_count: int = 0,
    global_count: int = 0,
) -> str:
    morning_lane = morning if morning in ("korea", "global") else "korea"
    afternoon_lane = afternoon if afternoon in ("korea", "global") else "global"
    if index <= 0:
        return morning_lane
    if index == 1:
        return afternoon_lane
    if night == "auto" or night not in ("korea", "global"):
        return weaker_source_lane(
            korea_count,
            global_count,
            afternoon=afternoon_lane,
        )
    return night


def analyzed_counts_by_lane(db, now_utc: datetime) -> tuple[int, int]:
    """Processed X posts since local midnight, split by discovery lane."""
    from app.db.models import RawItem

    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    local = now.astimezone(KST)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    korea = 0
    glob = 0
    rows = (
        db.query(RawItem.raw_payload)
        .filter(
            RawItem.provider == "x",
            RawItem.processed == 1,
            RawItem.fetched_at >= start_utc,
        )
        .all()
    )
    for (payload,) in rows:
        if isinstance(payload, str):
            continue
        lane = (payload or {}).get("source_lane")
        if lane == "korea":
            korea += 1
        elif lane == "global":
            glob += 1
    return korea, glob


def lanes_for_scan(
    industry_csv: str,
    source_lane: str,
    *,
    limit: int,
) -> list[TopicLane]:
    from app.pipeline.industries import parse_industry_keys

    keys = parse_industry_keys(industry_csv)
    lane = source_lane if source_lane in ("korea", "global") else "global"
    selected = [item for item in build_topic_lanes(keys) if item.source_lane == lane]
    cap = max(1, limit)
    return selected[:cap]


def advance_since_id(
    external_ids: list[str],
    *,
    previous: str | None,
    page_cap: int,
) -> str | None:
    """Move the cursor without skipping a full page of older ids.

    A short page means the query is caught up, so the cursor jumps to the
    newest id. A full page keeps the oldest returned id so the next scan can
    still see posts that this page did not include.
    """
    ids = [int(value) for value in external_ids if str(value).isdigit()]
    if not ids:
        return previous
    newest = max(ids)
    if len(ids) < page_cap:
        return str(newest)
    oldest = min(ids)
    if previous and str(previous).isdigit() and oldest <= int(previous):
        return str(newest)
    return str(oldest)


@dataclass(frozen=True)
class XFetchPlan:
    legacy: bool
    skip: bool
    reason: str
    slot_key: str | None
    slot_label: str | None
    lanes: list[TopicLane]
    run_accounts: bool
    run_dynamic: bool
    max_results: int
    hot_reply_spike: int
    hot_enabled: bool
    hot_max_hours: int
    mode: str


def kst_day(now_utc: datetime) -> str:
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    return now.astimezone(KST).strftime("%Y-%m-%d")


def posts_fetched_today(cursor_repo, now_utc: datetime) -> int:
    raw = cursor_repo.get("x", POSTS_DAY_KEY) or ""
    day, _, count = raw.partition("|")
    if day != kst_day(now_utc):
        return 0
    return int(count) if count.isdigit() else 0


def add_posts_fetched_today(cursor_repo, now_utc: datetime, count: int) -> int:
    total = posts_fetched_today(cursor_repo, now_utc) + max(0, int(count))
    cursor_repo.set("x", POSTS_DAY_KEY, f"{kst_day(now_utc)}|{total}")
    return total


def _scan_index(cursor_repo) -> int:
    raw = cursor_repo.get("x", SCAN_INDEX_KEY)
    return int(raw) if raw and str(raw).isdigit() else 0


def build_fetch_plan(
    config,
    cursor_repo,
    now_utc: datetime,
    *,
    korea_count: int = 0,
    global_count: int = 0,
    plans=None,
) -> XFetchPlan:
    """Decide which X calls this wake may make. Does not call X."""
    if config.scan_mode != "scheduled":
        return XFetchPlan(
            legacy=True,
            skip=False,
            reason="interval",
            slot_key=None,
            slot_label=None,
            lanes=[],
            run_accounts=True,
            run_dynamic=True,
            max_results=int(config.max_results or 10),
            hot_reply_spike=int(config.hot_reply_spike or 15),
            hot_enabled=bool(config.hot_enabled),
            hot_max_hours=int(config.hot_max_hours or 6),
            mode="interval",
        )
    last = cursor_repo.get("x", LAST_SLOT_KEY)
    slot = due_slot(
        now_utc,
        config.scan_hours_kst,
        window_minutes=int(config.scan_window_minutes or 40),
        last_slot_key=last,
    )
    hot_lanes = (
        _active_hot_lanes(config, cursor_repo, now_utc, plans=plans)
        if config.hot_enabled
        else []
    )
    if hot_lanes and slot is None and not _hot_due(config, cursor_repo, now_utc):
        hot_lanes = []
    if slot is None and not hot_lanes:
        return XFetchPlan(
            legacy=False,
            skip=True,
            reason="not_due",
            slot_key=None,
            slot_label=None,
            lanes=[],
            run_accounts=False,
            run_dynamic=False,
            max_results=int(config.max_results or 10),
            hot_reply_spike=int(config.hot_reply_spike or 15),
            hot_enabled=bool(config.hot_enabled),
            hot_max_hours=int(config.hot_max_hours or 6),
            mode="idle",
        )
    lanes: list[TopicLane] = []
    run_accounts = False
    run_dynamic = False
    label = "hot"
    key = None
    mode = "hot"
    if slot is not None:
        source = lane_for_slot(
            slot.index,
            config.morning_lane,
            config.afternoon_lane,
            config.night_lane,
            korea_count=korea_count,
            global_count=global_count,
        )
        if plans:
            from app.services.industry_search_config import select_rotation_lanes

            lanes.extend(
                select_rotation_lanes(
                    plans,
                    source,
                    scan_index=_scan_index(cursor_repo),
                    limit=int(config.lanes_per_scan or 10),
                    opposite_count=int(getattr(config, "opposite_lane_count", 2) or 0),
                )
            )
        else:
            lanes.extend(
                lanes_for_scan(
                    config.industries,
                    source,
                    limit=int(config.lanes_per_scan or 10),
                )
            )
        run_accounts = config.accounts_on == "all" or (
            config.accounts_on == "morning" and slot.index == 0
        ) or (
            config.accounts_on == "night"
            and slot.index == max(len(parse_scan_hours(config.scan_hours_kst)) - 1, 0)
        )
        run_dynamic = config.dynamic_mode == "normal"
        label = slot.label
        key = slot.key
        mode = "normal"
        cursor_repo.set("x", LAST_SLOT_KEY, slot.key)
        cursor_repo.set("x", SCAN_INDEX_KEY, str(_scan_index(cursor_repo) + 1))
    for lane in hot_lanes:
        if lane not in lanes:
            lanes.append(lane)
    if slot is None:
        run_dynamic = config.dynamic_mode == "hot"
        cursor_repo.set("x", "hot:last_fetch_at", _iso(now_utc))
    return XFetchPlan(
        legacy=False,
        skip=False,
        reason="due",
        slot_key=key,
        slot_label=label,
        lanes=lanes,
        run_accounts=run_accounts,
        run_dynamic=run_dynamic,
        max_results=int(config.max_results or 10),
        hot_reply_spike=int(config.hot_reply_spike or 15),
        hot_enabled=bool(config.hot_enabled),
        hot_max_hours=int(config.hot_max_hours or 6),
        mode=mode,
    )


def _hot_due(config, cursor_repo, now_utc: datetime) -> bool:
    raw = cursor_repo.get("x", "hot:last_fetch_at")
    if not raw:
        return True
    try:
        last = _parse(raw)
    except ValueError:
        return True
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    elapsed = (now - last).total_seconds()
    return elapsed >= int(config.hot_interval_minutes or 45) * 60


def _plan_query(plans, industry: str, source_lane: str) -> str | None:
    if not plans:
        return None
    for plan in plans:
        if getattr(plan, "key", None) != industry:
            continue
        if source_lane == "korea":
            return plan.query_ko or None
        return plan.query_en or None
    return None


def _active_hot_lanes(
    config, cursor_repo, now_utc: datetime, *, plans=None
) -> list[TopicLane]:
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    lanes: list[TopicLane] = []
    for key, raw in cursor_repo.list_prefix("x", HOT_PREFIX):
        parsed = decode_hot(raw)
        body = key[len(HOT_PREFIX) :]
        industry, _, source_lane = body.partition(":")
        if source_lane not in ("korea", "global"):
            continue
        if parsed is None or parsed[2] <= now or parsed[1] >= int(config.hot_idle_scans or 2):
            cursor_repo.delete("x", key)
            continue
        query = _plan_query(plans, industry, source_lane)
        if query:
            lanes.append(TopicLane(industry, source_lane, query))
        else:
            lanes.extend(lanes_for_scan(industry, source_lane, limit=1))
    return lanes


def arm_hot_topic(
    cursor_repo,
    *,
    industry_key: str,
    source_lane: str,
    now_utc: datetime,
    max_hours: int,
) -> None:
    key = hot_cursor_key(industry_key, source_lane)
    if cursor_repo.get("x", key):
        return
    now = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    until = now + timedelta(hours=max(1, max_hours))
    cursor_repo.set("x", key, encode_hot(started=now, idle=0, until=until))


def note_hot_result(
    cursor_repo,
    *,
    industry_key: str,
    source_lane: str,
    meaningful: bool,
    idle_limit: int,
) -> None:
    """Quiet polls end Hot. A new Issue or an evidence update resets the streak."""
    key = hot_cursor_key(industry_key, source_lane)
    raw = cursor_repo.get("x", key)
    parsed = decode_hot(raw)
    if parsed is None:
        return
    started, idle, until = parsed
    idle = 0 if meaningful else idle + 1
    if idle >= idle_limit:
        cursor_repo.delete("x", key)
        return
    cursor_repo.set("x", key, encode_hot(started=started, idle=idle, until=until))


POLLED_KEY = "schedule:hot_polled"


def remember_hot_polls(cursor_repo, lanes: list[str]) -> None:
    cleaned = [lane for lane in lanes if lane]
    if not cleaned:
        return
    existing = cursor_repo.get("x", POLLED_KEY) or ""
    merged = [part for part in existing.split("|") if part]
    for lane in cleaned:
        if lane not in merged:
            merged.append(lane)
    cursor_repo.set("x", POLLED_KEY, "|".join(merged))


def settle_hot_polls(
    cursor_repo,
    *,
    meaningful: set[str],
    idle_limit: int,
) -> None:
    raw = cursor_repo.get("x", POLLED_KEY) or ""
    cursor_repo.delete("x", POLLED_KEY)
    for lane in [part for part in raw.split("|") if part]:
        industry, _, source_lane = lane.partition(":")
        if not industry or not source_lane:
            continue
        note_hot_result(
            cursor_repo,
            industry_key=industry,
            source_lane=source_lane,
            meaningful=lane in meaningful,
            idle_limit=idle_limit,
        )


def allow_extra_page(*, mode: str, page_full: bool) -> bool:
    """One extra search page, and only while a topic is in Hot monitoring."""
    return mode == "hot" and page_full


def hot_cursor_key(industry_key: str, source_lane: str) -> str:
    return f"{HOT_PREFIX}{industry_key}:{source_lane}"


def encode_hot(*, started: datetime, idle: int, until: datetime) -> str:
    return (
        f"{_iso(started)}|{int(idle)}|{_iso(until)}"
    )


def decode_hot(raw: str | None) -> tuple[datetime, int, datetime] | None:
    if not raw or raw.count("|") != 2:
        return None
    started_s, idle_s, until_s = raw.split("|")
    try:
        return _parse(started_s), int(idle_s), _parse(until_s)
    except ValueError:
        return None


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
