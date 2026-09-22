"""Trend lifecycle: windowed internal, fresh AI, candidate vs transition."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import (
    IssueFollow,
    IssueView,
    MetricSnapshot,
    Participation,
    ParticipationOption,
    Signal,
)
from app.db.session import Base
from app.pipeline.trend_status import (
    TREND_NORMAL,
    TREND_RISING,
    TREND_TRENDING,
    apply_trend_state_transition,
    apply_trend_status,
    calculate_candidate_status,
    combine_trend_status,
    external_level_from_inputs,
    measure_recent_internal_interest,
    set_ai_trending_hint,
)
from app.pipeline.velocity import VelocityReading, compute_velocity, record_metric_snapshot


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _settings(**kwargs) -> Settings:
    base = dict(
        issue_trend_internal_window_hours=24.0,
        issue_trend_downgrade_grace_minutes=60.0,
        issue_trend_min_unique_opens=2,
        issue_trend_min_follows=1,
        issue_trend_min_participations=1,
    )
    base.update(kwargs)
    return Settings(**base)


def _issue(db, **kwargs) -> Signal:
    row = Signal(
        title=kwargs.get("title", "t"),
        summary=kwargs.get("summary", "summary text"),
        status="published",
        source_reply_peak=kwargs.get("source_reply_peak", 0),
        trend_status=kwargs.get("trend_status", "NORMAL"),
        trend_status_updated_at=kwargs.get("trend_status_updated_at"),
        is_trending=False,
        emphasis={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _fresh_snap(db, signal_id: str, *, likes: int = 10, replies: int = 0, when=None):
    when = when or datetime.utcnow()
    db.add(
        MetricSnapshot(
            signal_id=signal_id,
            reply_count=replies,
            like_count=likes,
            retweet_count=0,
            quote_count=0,
            engagement_score=float(likes) + float(replies) * 3.0,
            captured_at=when,
        )
    )
    db.commit()


def test_combine_requires_internal():
    assert combine_trend_status(TREND_TRENDING, False) == TREND_NORMAL
    assert combine_trend_status(TREND_TRENDING, True) == TREND_TRENDING
    assert combine_trend_status(TREND_RISING, True) == TREND_RISING
    assert combine_trend_status(TREND_NORMAL, True) == TREND_NORMAL


def test_external_velocity_or_fresh_ai():
    assert (
        external_level_from_inputs(velocity_status="TRENDING", fresh_ai_path=False)
        == TREND_TRENDING
    )
    assert (
        external_level_from_inputs(velocity_status="NORMAL", fresh_ai_path=True)
        == TREND_TRENDING
    )
    assert (
        external_level_from_inputs(velocity_status="RISING", fresh_ai_path=False)
        == TREND_RISING
    )
    assert (
        external_level_from_inputs(velocity_status="NORMAL", fresh_ai_path=False)
        == TREND_NORMAL
    )


def test_transition_upgrade_immediate_downgrade_one_step():
    cfg = _settings(issue_trend_downgrade_grace_minutes=60)
    now = datetime.utcnow()
    old = now - timedelta(minutes=90)
    assert (
        apply_trend_state_transition(
            TREND_NORMAL, TREND_RISING, status_updated_at=now, settings=cfg, now=now
        )
        == TREND_RISING
    )
    assert (
        apply_trend_state_transition(
            TREND_RISING, TREND_TRENDING, status_updated_at=now, settings=cfg, now=now
        )
        == TREND_TRENDING
    )
    # Within grace: hold
    assert (
        apply_trend_state_transition(
            TREND_TRENDING,
            TREND_NORMAL,
            status_updated_at=now - timedelta(minutes=10),
            settings=cfg,
            now=now,
        )
        == TREND_TRENDING
    )
    # After grace: one step only
    assert (
        apply_trend_state_transition(
            TREND_TRENDING,
            TREND_NORMAL,
            status_updated_at=old,
            settings=cfg,
            now=now,
        )
        == TREND_RISING
    )
    assert (
        apply_trend_state_transition(
            TREND_RISING,
            TREND_NORMAL,
            status_updated_at=old,
            settings=cfg,
            now=now,
        )
        == TREND_NORMAL
    )


def test_case1_external_high_internal_zero_stays_normal():
    db = _session()
    cfg = _settings()
    sig = _issue(db)
    t0 = datetime.utcnow() - timedelta(hours=1)
    db.add(
        MetricSnapshot(
            signal_id=sig.id,
            reply_count=0,
            like_count=0,
            engagement_score=0.0,
            captured_at=t0,
        )
    )
    db.commit()
    record_metric_snapshot(db, signal_id=sig.id, reply_count=40, like_count=100)
    reading = compute_velocity(db, sig.id)
    assert reading.trend_status == TREND_TRENDING
    res = apply_trend_status(
        db, sig, velocity=reading, ai_trending=True, settings=cfg
    )
    assert res.external_level == TREND_TRENDING
    assert res.internal.passed is False
    assert res.candidate_status == TREND_NORMAL
    assert res.final_status == TREND_NORMAL
    assert sig.is_trending is False


def test_normal_to_rising_immediate():
    db = _session()
    cfg = _settings()
    sig = _issue(db)
    db.add(IssueFollow(user_id="u1", signal_id=sig.id))
    db.commit()
    vel = VelocityReading(8.0, 0.0, TREND_RISING)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg)
    assert res.candidate_status == TREND_RISING
    assert res.final_status == TREND_RISING
    assert sig.trend_status == TREND_RISING
    assert sig.trend_status_updated_at is not None


def test_rising_to_trending_immediate():
    db = _session()
    cfg = _settings()
    now = datetime.utcnow()
    sig = _issue(
        db, trend_status=TREND_RISING, trend_status_updated_at=now - timedelta(minutes=5)
    )
    db.add(IssueFollow(user_id="u1", signal_id=sig.id))
    db.commit()
    vel = VelocityReading(25.0, 90.0, TREND_TRENDING)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert res.final_status == TREND_TRENDING
    assert sig.is_trending is True


def test_trending_to_rising_after_grace_one_step():
    db = _session()
    cfg = _settings(issue_trend_downgrade_grace_minutes=60)
    now = datetime.utcnow()
    sig = _issue(
        db,
        trend_status=TREND_TRENDING,
        trend_status_updated_at=now - timedelta(minutes=90),
    )
    db.add(IssueFollow(user_id="u1", signal_id=sig.id))
    db.commit()
    vel = VelocityReading(0.0, 0.0, TREND_NORMAL)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert res.candidate_status == TREND_NORMAL
    assert res.final_status == TREND_RISING  # one step, not NORMAL


def test_trending_candidate_normal_holds_inside_grace():
    db = _session()
    cfg = _settings(issue_trend_downgrade_grace_minutes=60)
    now = datetime.utcnow()
    sig = _issue(
        db,
        trend_status=TREND_TRENDING,
        trend_status_updated_at=now - timedelta(minutes=10),
    )
    db.add(IssueFollow(user_id="u1", signal_id=sig.id))
    db.commit()
    vel = VelocityReading(0.0, 0.0, TREND_NORMAL)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert res.candidate_status == TREND_NORMAL
    assert res.final_status == TREND_TRENDING


def test_rising_to_normal_after_grace():
    db = _session()
    cfg = _settings(issue_trend_downgrade_grace_minutes=60)
    now = datetime.utcnow()
    sig = _issue(
        db,
        trend_status=TREND_RISING,
        trend_status_updated_at=now - timedelta(minutes=90),
    )
    # no internal
    vel = VelocityReading(0.0, 0.0, TREND_NORMAL)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert res.final_status == TREND_NORMAL


def test_fresh_ai_path_with_snapshot_no_reply_threshold():
    """AI TRENDING uses fresh hint + snapshot activity — likes enough, replies not required."""
    db = _session()
    cfg = _settings()
    now = datetime.utcnow()
    sig = _issue(db)
    set_ai_trending_hint(sig, True, when=now)
    _fresh_snap(db, sig.id, likes=12, replies=0, when=now)
    db.add(IssueFollow(user_id="u1", signal_id=sig.id, created_at=now))
    db.commit()
    cand = calculate_candidate_status(
        db, sig, velocity=VelocityReading(0, 0, TREND_NORMAL), settings=cfg, now=now
    )
    assert cand.external_level == TREND_TRENDING
    assert cand.candidate_status == TREND_TRENDING


def test_stale_ai_hint_no_promotion():
    db = _session()
    cfg = _settings(issue_trend_internal_window_hours=24)
    now = datetime.utcnow()
    sig = _issue(db)
    set_ai_trending_hint(sig, True, when=now - timedelta(hours=48))
    _fresh_snap(db, sig.id, likes=20, when=now)
    db.add(IssueFollow(user_id="u1", signal_id=sig.id, created_at=now))
    db.commit()
    cand = calculate_candidate_status(
        db, sig, velocity=VelocityReading(0, 0, TREND_NORMAL), settings=cfg, now=now
    )
    assert cand.external_level == TREND_NORMAL


def test_ai_false_clears_timestamp():
    db = _session()
    sig = _issue(db)
    set_ai_trending_hint(sig, True)
    assert (sig.emphasis or {}).get("ai_trending") is True
    assert (sig.emphasis or {}).get("ai_trending_at")
    set_ai_trending_hint(sig, False)
    assert (sig.emphasis or {}).get("ai_trending") is False
    assert (sig.emphasis or {}).get("ai_trending_at") is None


def test_stale_snapshot_velocity_treated_normal():
    db = _session()
    cfg = _settings(issue_trend_internal_window_hours=24)
    now = datetime.utcnow()
    sig = _issue(db)
    old = now - timedelta(hours=48)
    db.add(
        MetricSnapshot(
            signal_id=sig.id,
            reply_count=0,
            like_count=0,
            engagement_score=0.0,
            captured_at=old - timedelta(hours=1),
        )
    )
    db.add(
        MetricSnapshot(
            signal_id=sig.id,
            reply_count=50,
            like_count=100,
            engagement_score=250.0,
            captured_at=old,
        )
    )
    db.add(IssueFollow(user_id="u1", signal_id=sig.id, created_at=now))
    db.commit()
    # Explicit high velocity reading, but snaps are stale → external NORMAL
    vel = VelocityReading(40.0, 100.0, TREND_TRENDING)
    cand = calculate_candidate_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert cand.external_level == TREND_NORMAL


def test_old_follow_excluded_recent_follow_included():
    db = _session()
    cfg = _settings(issue_trend_internal_window_hours=24)
    now = datetime.utcnow()
    sig = _issue(db)
    db.add(
        IssueFollow(
            user_id="old",
            signal_id=sig.id,
            created_at=now - timedelta(hours=48),
        )
    )
    db.commit()
    internal = measure_recent_internal_interest(db, sig.id, settings=cfg, now=now)
    assert internal.recent_follow == 0
    assert internal.passed is False

    db.add(IssueFollow(user_id="new", signal_id=sig.id, created_at=now))
    db.commit()
    internal2 = measure_recent_internal_interest(db, sig.id, settings=cfg, now=now)
    assert internal2.recent_follow == 1
    assert internal2.passed is True
    # Old follow row still present (personal interest not deleted)
    assert db.query(IssueFollow).filter(IssueFollow.signal_id == sig.id).count() == 2


def test_recent_vote_and_open():
    db = _session()
    cfg = _settings(issue_trend_internal_window_hours=24)
    now = datetime.utcnow()
    sig = _issue(db)
    opt = ParticipationOption(signal_id=sig.id, label="A", display_order=0)
    db.add(opt)
    db.commit()
    db.refresh(opt)
    db.add(
        Participation(
            signal_id=sig.id,
            user_id="u1",
            option_id=opt.id,
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        IssueView(
            user_id="v1",
            signal_id=sig.id,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db.add(
        IssueView(
            user_id="v2",
            signal_id=sig.id,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db.commit()
    internal = measure_recent_internal_interest(db, sig.id, settings=cfg, now=now)
    assert internal.recent_vote == 1
    assert internal.recent_open == 2
    assert internal.passed is True


def test_reactivation_from_normal():
    db = _session()
    cfg = _settings()
    now = datetime.utcnow()
    sig = _issue(
        db,
        trend_status=TREND_NORMAL,
        trend_status_updated_at=now - timedelta(hours=5),
    )
    db.add(IssueFollow(user_id="u1", signal_id=sig.id, created_at=now))
    db.commit()
    vel = VelocityReading(8.0, 0.0, TREND_RISING)
    res = apply_trend_status(db, sig, velocity=vel, settings=cfg, now=now)
    assert res.final_status == TREND_RISING


def test_candidate_ignores_current_status():
    db = _session()
    cfg = _settings()
    now = datetime.utcnow()
    sig = _issue(db, trend_status=TREND_TRENDING, trend_status_updated_at=now)
    # No internal, no external → candidate NORMAL even though current TRENDING
    cand = calculate_candidate_status(
        db, sig, velocity=VelocityReading(0, 0, TREND_NORMAL), settings=cfg, now=now
    )
    assert cand.candidate_status == TREND_NORMAL
    assert cand.final_status == TREND_NORMAL  # calculate returns candidate in final too


def test_status_updated_at_only_on_change():
    db = _session()
    cfg = _settings()
    now = datetime.utcnow()
    stamped = now - timedelta(hours=1)
    sig = _issue(db, trend_status=TREND_NORMAL, trend_status_updated_at=stamped)
    res = apply_trend_status(
        db,
        sig,
        velocity=VelocityReading(0, 0, TREND_NORMAL),
        settings=cfg,
        now=now,
    )
    assert res.final_status == TREND_NORMAL
    assert sig.trend_status_updated_at == stamped
