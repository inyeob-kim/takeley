"""Issue retention loop: follow / view / content_updated_at / has_new_update / push."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import (
    DeviceToken,
    IssueFollow,
    IssueUserEvent,
    IssueView,
    Participation,
    PushNotification,
    Signal,
    UserPreference,
)
from app.db.session import Base
from app.services.issue_service import (
    IssueService,
    replace_participation_options,
    touch_content_updated,
)
from app.services.push_enqueue_service import enqueue_issue_update


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _published_issue(db: Session, *, title: str = "테스트 이슈") -> Signal:
    now = datetime.utcnow() - timedelta(hours=2)
    signal = Signal(
        title=title,
        summary="요약",
        why_it_matters="왜",
        key_points=["포인트"],
        status="published",
        importance=0.8,
        confidence=0.7,
        trend_score=0.5,
        category="Tech",
        topic="test",
        participation_suitable=True,
        participation_type="binary",
        participation_question="어떻게 생각하세요?",
        published_at=now,
        first_seen_at=now,
        content_updated_at=now,
        updated_at=now,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    replace_participation_options(db, signal, ["찬성", "반대"])
    db.commit()
    db.refresh(signal)
    return signal


def test_a_open_vote_follow_no_false_update():
    """Scenario A: open → vote → follow → has_new_update = false."""
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-a"

    svc.record_view(signal.id, user_id=uid)
    opt = signal.participation_options[0]
    svc.participate(signal.id, user_id=uid, option_id=opt.id)
    out = svc.follow(signal.id, user_id=uid)
    assert out is not None
    assert out.is_following is True
    assert out.has_new_update is False

    # Past content_updated_at must not light up as new after fresh follow.
    detail = svc.get_issue(signal.id, user_id=uid)
    assert detail is not None
    assert detail.has_new_update is False


def test_b_semantic_update_sets_has_new_update():
    """Scenario B: semantic UPDATE bumps content_updated_at → has_new_update."""
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-b"

    svc.follow(signal.id, user_id=uid)
    before = signal.content_updated_at
    assert before is not None

    touch_content_updated(signal, datetime.utcnow() + timedelta(seconds=1))
    db.commit()

    detail = svc.get_issue(signal.id, user_id=uid)
    assert detail is not None
    assert detail.has_new_update is True
    assert signal.content_updated_at > before


def test_c_view_clears_flag_on_next_get():
    """Scenario C (backend half): after /view, next GET has_new_update=false.

    UI banner snapshot is frontend-only; backend must clear the flag after view.
    """
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-c"

    svc.follow(signal.id, user_id=uid)
    # Content bump must be after interest_started_at but before the later /view clock.
    touch_content_updated(signal, datetime.utcnow())
    db.commit()

    before = svc.get_issue(signal.id, user_id=uid)
    assert before is not None
    assert before.has_new_update is True

    time.sleep(0.02)
    viewed = svc.record_view(signal.id, user_id=uid)
    assert viewed is not None
    after = svc.get_issue(signal.id, user_id=uid)
    assert after is not None
    assert after.has_new_update is False


def test_d_impression_does_not_touch_view_or_content():
    """Scenario D: impression must not change last_seen_at or content_updated_at."""
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-d"
    content_before = signal.content_updated_at

    svc.follow(signal.id, user_id=uid)
    ev = svc.record_event(signal.id, "impression", user_id=uid)
    assert ev is not None
    assert ev["impression_count"] == 1

    db.refresh(signal)
    assert signal.content_updated_at == content_before
    assert (
        db.query(IssueView)
        .filter(IssueView.user_id == uid, IssueView.signal_id == signal.id)
        .first()
        is None
    )
    detail = svc.get_issue(signal.id, user_id=uid)
    assert detail is not None
    assert detail.has_new_update is False


def test_e_issue_update_push_dedupe_hour_bucket():
    """Scenario E: multiple UPDATE enqueues within same hour → at most 1 push."""
    db = _session()
    signal = _published_issue(db, title="팔로우 이슈 제목")
    uid = "user-e"
    db.add(
        UserPreference(
            user_id=uid,
            brief_alarm_time="07:00",
            timezone="Asia/Seoul",
            notifications_enabled=True,
            updated_at=datetime.utcnow(),
        )
    )
    db.add(
        DeviceToken(
            user_id=uid,
            fcm_token="f" * 40,
            platform="web",
            is_active=True,
        )
    )
    db.add(IssueFollow(user_id=uid, signal_id=signal.id))
    db.commit()

    first = enqueue_issue_update(db, signal_id=signal.id, title=signal.title or "")
    second = enqueue_issue_update(db, signal_id=signal.id, title=signal.title or "")
    assert first["enqueued"] == 1
    assert second["enqueued"] == 0
    assert second["skipped_dedupe"] == 1
    rows = (
        db.query(PushNotification)
        .filter(PushNotification.user_id == uid, PushNotification.category == "issue_update")
        .all()
    )
    assert len(rows) == 1
    assert "새로운 소식이 추가됐어요" in (rows[0].title or "")
    assert "뉴스" not in (rows[0].title or "")


def test_follow_duplicate_and_unfollow():
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-follow"

    a = svc.follow(signal.id, user_id=uid)
    b = svc.follow(signal.id, user_id=uid)
    assert a is not None and b is not None
    assert a.is_following is True
    assert (
        db.query(IssueFollow)
        .filter(IssueFollow.user_id == uid, IssueFollow.signal_id == signal.id)
        .count()
        == 1
    )

    c = svc.unfollow(signal.id, user_id=uid)
    assert c is not None
    assert c.is_following is False
    assert (
        db.query(IssueFollow)
        .filter(IssueFollow.user_id == uid, IssueFollow.signal_id == signal.id)
        .count()
        == 0
    )


def test_vote_option_change_keeps_single_participation():
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-vote"
    o0, o1 = signal.participation_options[0], signal.participation_options[1]

    svc.participate(signal.id, user_id=uid, option_id=o0.id)
    again = svc.participate(signal.id, user_id=uid, option_id=o1.id)
    assert again is not None
    assert again["my_option_id"] == o0.id
    assert again["participation_count"] == 1
    assert (
        db.query(Participation)
        .filter(Participation.user_id == uid, Participation.signal_id == signal.id)
        .count()
        == 1
    )


def test_activity_followed_and_participated():
    db = _session()
    signal = _published_issue(db)
    other = _published_issue(db, title="다른 이슈")
    svc = IssueService(db)
    uid = "user-act"

    opt = signal.participation_options[0]
    svc.participate(signal.id, user_id=uid, option_id=opt.id)
    svc.follow(signal.id, user_id=uid)
    svc.follow(other.id, user_id=uid)

    activity = svc.my_activity(uid)
    assert len(activity.participations) == 1
    assert activity.participations[0].id == signal.id
    follow_ids = {x.id for x in activity.followed}
    assert signal.id in follow_ids
    assert other.id in follow_ids


def test_evidence_after_follow_shows_update():
    """Follow then new evidence → has_new_update true."""
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-ev"

    svc.follow(signal.id, user_id=uid)
    assert svc.get_issue(signal.id, user_id=uid).has_new_update is False

    touch_content_updated(signal, datetime.utcnow() + timedelta(minutes=5))
    db.commit()
    assert svc.get_issue(signal.id, user_id=uid).has_new_update is True


def test_list_path_bulk_loads_no_n_plus_one():
    """list_issues must not query follow/view/participation per issue."""
    db = _session()
    signals = [_published_issue(db, title=f"이슈 {i}") for i in range(5)]
    uid = "user-n1"
    for s in signals[:3]:
        IssueService(db).follow(s.id, user_id=uid)

    engine = db.get_bind()
    statements: list[str] = []

    def _before_cursor(conn, cursor, statement, parameters, context, executemany):
        statements.append(str(statement))

    event.listen(engine, "before_cursor_execute", _before_cursor)
    try:
        listed = IssueService(db).list_issues(limit=10, sort="trending", user_id=uid)
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor)

    assert listed.count >= 5
    follow_selects = [
        s
        for s in statements
        if "issue_follows" in s.lower() and s.lstrip().upper().startswith("SELECT")
    ]
    view_selects = [
        s
        for s in statements
        if "issue_views" in s.lower() and s.lstrip().upper().startswith("SELECT")
    ]
    # Bulk IN (...) — one SELECT each, not one per issue.
    assert len(follow_selects) <= 2
    assert len(view_selects) <= 2


def test_funnel_events_appended():
    db = _session()
    signal = _published_issue(db)
    svc = IssueService(db)
    uid = "user-funnel"

    svc.record_view(signal.id, user_id=uid)
    opt = signal.participation_options[0]
    svc.participate(signal.id, user_id=uid, option_id=opt.id)
    svc.follow(signal.id, user_id=uid)
    svc.record_event(signal.id, "impression", user_id=uid)

    events = {
        r.event
        for r in db.query(IssueUserEvent)
        .filter(IssueUserEvent.user_id == uid, IssueUserEvent.signal_id == signal.id)
        .all()
    }
    assert "open" in events
    assert "vote" in events
    assert "follow" in events
    assert "impression" in events


def test_touch_content_updated_independent_of_orm_updated_at():
    db = _session()
    signal = _published_issue(db)
    content_before = signal.content_updated_at
    # Counter-style mutation should not use touch_content_updated.
    signal.impression_count = int(signal.impression_count or 0) + 1
    signal.updated_at = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    db.refresh(signal)
    assert signal.content_updated_at == content_before
