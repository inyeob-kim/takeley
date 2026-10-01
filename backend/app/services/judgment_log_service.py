"""Judgment log, streak, daily recap, and closure cards (participation Phase 4–5)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.models import (
    Participation,
    ParticipationChangeLog,
    ParticipationOption,
    Signal,
)

KST = ZoneInfo("Asia/Seoul")

UNLOCK_LOCKED = "locked"
UNLOCK_BASIC = "basic"
UNLOCK_FULL = "full"


def _as_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def kst_date(dt: datetime) -> date:
    """Calendar date in Asia/Seoul (pipeline stores naive UTC)."""
    utc = _as_utc_naive(dt).replace(tzinfo=timezone.utc)
    return utc.astimezone(KST).date()


def kst_today() -> date:
    return datetime.now(timezone.utc).astimezone(KST).date()


def kst_day_start_utc_naive(d: date) -> datetime:
    """Midnight KST for date d, as naive UTC (matches DB timestamps)."""
    local = datetime(d.year, d.month, d.day, tzinfo=KST)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def vote_count(db: Session, user_id: str) -> int:
    return (
        db.query(Participation)
        .filter(Participation.user_id == user_id)
        .count()
    )


def unlock_level(vote_n: int) -> str:
    settings = get_settings()
    basic = max(1, int(settings.judgment_log_unlock_basic))
    full = max(basic, int(settings.judgment_log_unlock_full))
    if vote_n >= full:
        return UNLOCK_FULL
    if vote_n >= basic:
        return UNLOCK_BASIC
    return UNLOCK_LOCKED


def compute_streak_days(db: Session, user_id: str) -> int:
    """Consecutive KST calendar days with at least one participation change or vote."""
    logs = (
        db.query(ParticipationChangeLog.changed_at)
        .filter(ParticipationChangeLog.user_id == user_id)
        .order_by(ParticipationChangeLog.changed_at.desc())
        .limit(400)
        .all()
    )
    parts = (
        db.query(Participation.created_at, Participation.updated_at)
        .filter(Participation.user_id == user_id)
        .all()
    )
    days: set[date] = set()
    for (changed_at,) in logs:
        if changed_at:
            days.add(kst_date(changed_at))
    for created_at, updated_at in parts:
        if created_at:
            days.add(kst_date(created_at))
        if updated_at:
            days.add(kst_date(updated_at))
    if not days:
        return 0
    today = kst_today()
    # Streak may include today or end yesterday (still active until day rolls).
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _option_labels(db: Session, signal_ids: list[str]) -> dict[str, str]:
    if not signal_ids:
        return {}
    rows = (
        db.query(ParticipationOption)
        .filter(ParticipationOption.signal_id.in_(signal_ids))
        .all()
    )
    return {o.id: o.label for o in rows}


def _change_counts(db: Session, user_id: str, signal_ids: list[str]) -> dict[str, int]:
    if not signal_ids:
        return {}
    rows = (
        db.query(ParticipationChangeLog.signal_id)
        .filter(
            ParticipationChangeLog.user_id == user_id,
            ParticipationChangeLog.signal_id.in_(signal_ids),
        )
        .all()
    )
    out: dict[str, int] = {}
    for (sid,) in rows:
        out[sid] = out.get(sid, 0) + 1
    return out


def _recent_changes(
    db: Session, user_id: str, signal_id: str, *, limit: int = 5
) -> list[dict]:
    labels = _option_labels(db, [signal_id])
    rows = (
        db.query(ParticipationChangeLog)
        .filter(
            ParticipationChangeLog.user_id == user_id,
            ParticipationChangeLog.signal_id == signal_id,
        )
        .order_by(ParticipationChangeLog.changed_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        items.append(
            {
                "from_option_id": row.from_option_id,
                "from_label": labels.get(row.from_option_id or "", None),
                "to_option_id": row.to_option_id,
                "to_label": labels.get(row.to_option_id, ""),
                "changed_at": row.changed_at,
            }
        )
    return items


class JudgmentLogService:
    def __init__(self, db: Session):
        self.db = db

    def list_judgments(self, user_id: str, *, limit: int = 40) -> dict:
        settings = get_settings()
        votes = vote_count(self.db, user_id)
        level = unlock_level(votes)
        streak = compute_streak_days(self.db, user_id)

        # Locked: only last 3 title/stance; basic+: full list with notes; full+: changes.
        fetch_limit = 3 if level == UNLOCK_LOCKED else max(1, min(limit, 50))
        rows = (
            self.db.query(Participation)
            .options(joinedload(Participation.option), joinedload(Participation.signal))
            .filter(Participation.user_id == user_id)
            .order_by(Participation.updated_at.desc())
            .limit(fetch_limit)
            .all()
        )
        signal_ids = [r.signal_id for r in rows]
        change_n = _change_counts(self.db, user_id, signal_ids)
        items = []
        for row in rows:
            signal = row.signal
            title = (signal.title if signal else "") or ""
            option_label = (row.option.label if row.option else "") or ""
            item = {
                "issue_id": row.signal_id,
                "title": title,
                "option_id": row.option_id,
                "option_label": option_label,
                "note": None,
                "note_locked": level == UNLOCK_LOCKED,
                "updated_at": row.updated_at or row.created_at,
                "change_count": None,
                "changes": None,
                "changes_locked": level != UNLOCK_FULL,
            }
            if level in (UNLOCK_BASIC, UNLOCK_FULL):
                item["note"] = (row.note or "").strip() or None
                item["note_locked"] = False
            if level == UNLOCK_FULL:
                item["change_count"] = change_n.get(row.signal_id, 0)
                item["changes"] = _recent_changes(self.db, user_id, row.signal_id)
                item["changes_locked"] = False
            items.append(item)

        return {
            "unlock_level": level,
            "vote_count": votes,
            "streak_days": streak,
            "unlock_basic_at": int(settings.judgment_log_unlock_basic),
            "unlock_full_at": int(settings.judgment_log_unlock_full),
            "items": items,
        }

    def recap_today(self, user_id: str) -> dict:
        today = kst_today()
        start = kst_day_start_utc_naive(today)
        end = kst_day_start_utc_naive(today + timedelta(days=1))
        streak = compute_streak_days(self.db, user_id)
        rows = (
            self.db.query(Participation)
            .options(joinedload(Participation.option), joinedload(Participation.signal))
            .filter(
                Participation.user_id == user_id,
                Participation.updated_at >= start,
                Participation.updated_at < end,
            )
            .order_by(Participation.updated_at.desc())
            .limit(20)
            .all()
        )
        items = []
        for row in rows:
            signal = row.signal
            items.append(
                {
                    "issue_id": row.signal_id,
                    "title": (signal.title if signal else "") or "",
                    "option_label": (row.option.label if row.option else "") or "",
                    "note": (row.note or "").strip() or None,
                    "updated_at": row.updated_at or row.created_at,
                }
            )
        return {
            "date": today.isoformat(),
            "streak_days": streak,
            "vote_count_today": len(items),
            "items": items,
        }

    def closures_me(self, user_id: str, *, limit: int = 5) -> dict:
        """STALE lifecycle, or soft-stale: published 14+ days ago."""
        from sqlalchemy import and_, or_

        soft_before = datetime.utcnow() - timedelta(days=14)
        rows = (
            self.db.query(Participation)
            .join(Signal, Signal.id == Participation.signal_id)
            .options(joinedload(Participation.option), joinedload(Participation.signal))
            .filter(
                Participation.user_id == user_id,
                Signal.status == "published",
                or_(
                    Signal.lifecycle == "STALE",
                    and_(
                        Signal.published_at.isnot(None),
                        Signal.published_at < soft_before,
                        Signal.lifecycle.is_distinct_from("ARCHIVED"),
                    ),
                ),
            )
            .order_by(Participation.updated_at.desc())
            .limit(max(1, min(limit, 10)))
            .all()
        )
        items = []
        for row in rows:
            signal = row.signal
            life = (signal.lifecycle if signal else None) or "STALE"
            if life not in ("STALE", "ARCHIVED"):
                life = "STALE"
            items.append(
                {
                    "issue_id": row.signal_id,
                    "title": (signal.title if signal else "") or "",
                    "option_label": (row.option.label if row.option else "") or "",
                    "note": (row.note or "").strip() or None,
                    "lifecycle": life,
                    "updated_at": row.updated_at or row.created_at,
                }
            )
        return {"items": items}
