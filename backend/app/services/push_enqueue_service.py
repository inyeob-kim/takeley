"""Enqueue issue pushes into DB. Never calls FCM (worker sends)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    DeviceToken,
    PushNotification,
)
from app.services.preference_service import PreferenceService
from app.services.push_template_service import render_push_copy

logger = logging.getLogger(__name__)

CATEGORY_SIGNAL_NEW = "signal_new"
CATEGORY_ISSUE_UPDATE = "issue_update"


def _notifications_on(db: Session, user_id: str) -> bool:
    return PreferenceService(db).get(user_id).notifications_enabled


def _has_active_token(db: Session, user_id: str) -> bool:
    return (
        db.query(DeviceToken.id)
        .filter(DeviceToken.user_id == user_id, DeviceToken.is_active.is_(True))
        .first()
        is not None
    )


def _insert_pending(
    db: Session,
    *,
    user_id: str,
    category: str,
    title: str,
    body: str,
    data: dict,
    dedupe_key: str,
) -> PushNotification | None:
    existing = (
        db.query(PushNotification.id)
        .filter(PushNotification.dedupe_key == dedupe_key)
        .first()
    )
    if existing:
        logger.debug("push skip reason=dedupe key=%s", dedupe_key)
        return None
    row = PushNotification(
        user_id=user_id,
        category=category,
        title=title,
        body=body,
        data=data,
        dedupe_key=dedupe_key,
        status="pending",
        scheduled_at=datetime.utcnow(),
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        logger.exception("push enqueue failed key=%s", dedupe_key)
        return None
    logger.info(
        "push enqueued category=%s user=%s key=%s",
        category,
        user_id,
        dedupe_key,
    )
    return row


def _signal_push_count_today(db: Session, user_id: str, local_date: str) -> int:
    """Count signal_new rows already queued/sent for the user's local calendar day."""
    rows = (
        db.query(PushNotification)
        .filter(
            PushNotification.user_id == user_id,
            PushNotification.category == CATEGORY_SIGNAL_NEW,
            PushNotification.status.in_(("pending", "sent")),
        )
        .all()
    )
    count = 0
    for row in rows:
        data = row.data or {}
        if data.get("local_date") == local_date:
            count += 1
            continue
        if row.created_at and row.created_at.strftime("%Y-%m-%d") == local_date:
            count += 1
    return count


def users_for_issue_broadcast(db: Session) -> set[str]:
    """TAKELEY: new Issues go to all active device users (prefs/token filtered later)."""
    from app.db.models import User

    rows = (
        db.query(User.id)
        .filter(User.status == "active")
        .all()
    )
    return {uid for (uid,) in rows if uid}


def enqueue_signal_new(
    db: Session,
    *,
    signal_id: str,
    title: str | None = None,
    summary: str | None = None,
    related_symbols: list[str] | None = None,
    evidence_level: str = "UNVERIFIED",
    participation_suitable: bool = False,
    participation_question: str | None = None,
    trend_status: str | None = None,
    is_trending: bool = False,
    push_title: str | None = None,
    push_body: str | None = None,
) -> dict:
    """Fan out signal_new pushes. Prefs, FCM token, daily cap, and dedupe gate delivery."""
    from types import SimpleNamespace

    from app.services.push_copy import (
        PUSH_BODY_MAX,
        PUSH_TITLE_MAX,
        build_signal_new_copy,
    )

    settings = get_settings()
    related_symbols = related_symbols or []

    # Prefer live Issue row when present (override + metadata).
    from app.db.models import Signal

    row = db.query(Signal).filter(Signal.id == signal_id).first()
    if row:
        source = row
    else:
        source = SimpleNamespace(
            id=signal_id,
            title=title,
            participation_suitable=participation_suitable,
            participation_question=participation_question,
            trend_status=trend_status,
            is_trending=is_trending,
            push_title=push_title,
            push_body=push_body,
        )

    copy = build_signal_new_copy(source)
    # summary is intentionally unused — retained only for call-site compat.
    _ = summary

    user_ids = users_for_issue_broadcast(db)
    prefs = PreferenceService(db)
    enqueued = 0
    skipped_cap = 0
    skipped_prefs = 0
    skipped_token = 0
    skipped_dedupe = 0

    symbols_csv = ",".join(sorted({s.upper() for s in related_symbols if s}))
    title_limit = int(getattr(settings, "push_title_max", PUSH_TITLE_MAX) or PUSH_TITLE_MAX)
    body_limit = int(getattr(settings, "push_body_max", PUSH_BODY_MAX) or PUSH_BODY_MAX)
    push_title_out, body = render_push_copy(
        db,
        CATEGORY_SIGNAL_NEW,
        {
            "title": copy.title,
            "body": copy.body,
            "summary": "",  # never dump summary into push
            "symbols": symbols_csv,
            "signal_id": signal_id,
            "brief_date": "",
        },
        title_limit=title_limit,
        body_limit=body_limit,
    )

    for user_id in sorted(user_ids):
        if not _notifications_on(db, user_id):
            skipped_prefs += 1
            continue
        if not _has_active_token(db, user_id):
            skipped_token += 1
            continue
        local_date = prefs.local_brief_date(user_id)
        if _signal_push_count_today(db, user_id, local_date) >= settings.signal_push_daily_cap:
            skipped_cap += 1
            logger.info(
                "push skip reason=daily_cap category=signal_new user=%s date=%s",
                user_id,
                local_date,
            )
            continue
        dedupe_key = f"{user_id}:{CATEGORY_SIGNAL_NEW}:{signal_id}"
        row_n = _insert_pending(
            db,
            user_id=user_id,
            category=CATEGORY_SIGNAL_NEW,
            title=push_title_out,
            body=body,
            data={
                "category": CATEGORY_SIGNAL_NEW,
                "signal_id": signal_id,
                "issue_id": signal_id,
                "push_kind": copy.kind,
                "symbols": symbols_csv,
                "route": f"/issues/{signal_id}",
                "user_id": user_id,
                "local_date": local_date,
                "evidence_level": evidence_level,
            },
            dedupe_key=dedupe_key,
        )
        if row_n:
            enqueued += 1
        else:
            skipped_dedupe += 1

    result = {
        "signal_id": signal_id,
        "targets": len(user_ids),
        "enqueued": enqueued,
        "skipped_cap": skipped_cap,
        "skipped_prefs": skipped_prefs,
        "skipped_token": skipped_token,
        "skipped_dedupe": skipped_dedupe,
        "push_kind": copy.kind,
    }
    logger.info("signal_push_fanout %s", result)
    return result


def enqueue_issue_update(
    db: Session,
    *,
    signal_id: str,
    title: str,
) -> dict:
    """Best-effort fanout to Issue followers. Safe to call after UPDATE commit."""
    from app.db.models import IssueFollow

    from app.services.push_copy import PUSH_TITLE_MAX, clip_push_text

    settings = get_settings()
    _ = settings  # reserved for future caps
    follower_ids = [
        r.user_id
        for r in db.query(IssueFollow.user_id)
        .filter(IssueFollow.signal_id == signal_id)
        .all()
    ]
    if not follower_ids:
        return {"signal_id": signal_id, "targets": 0, "enqueued": 0, "skipped_dedupe": 0}

    now = datetime.utcnow()
    hour_bucket = now.strftime("%Y%m%d%H")
    enqueued = 0
    skipped_dedupe = 0
    skipped_prefs = 0
    skipped_token = 0
    issue_title = clip_push_text(title, PUSH_TITLE_MAX) or "이슈"

    for user_id in follower_ids:
        try:
            if not _notifications_on(db, user_id):
                skipped_prefs += 1
                continue
            if not _has_active_token(db, user_id):
                skipped_token += 1
                continue
            # 60-minute bucket via hour key — prevents UPDATE spam.
            dedupe_key = f"{user_id}:{CATEGORY_ISSUE_UPDATE}:{signal_id}:{hour_bucket}"
            row = _insert_pending(
                db,
                user_id=user_id,
                category=CATEGORY_ISSUE_UPDATE,
                title="내가 팔로우한 이슈에 새로운 소식이 추가됐어요.",
                body=issue_title,
                data={
                    "category": CATEGORY_ISSUE_UPDATE,
                    "signal_id": signal_id,
                    "issue_id": signal_id,
                    "route": f"/issues/{signal_id}",
                    "user_id": user_id,
                },
                dedupe_key=dedupe_key,
            )
            if row:
                enqueued += 1
            else:
                skipped_dedupe += 1
        except Exception:
            logger.exception(
                "issue_update push enqueue failed user=%s signal=%s",
                user_id,
                signal_id,
            )

    result = {
        "signal_id": signal_id,
        "targets": len(follower_ids),
        "enqueued": enqueued,
        "skipped_dedupe": skipped_dedupe,
        "skipped_prefs": skipped_prefs,
        "skipped_token": skipped_token,
    }
    logger.info("issue_update_push_fanout %s", result)
    return result
