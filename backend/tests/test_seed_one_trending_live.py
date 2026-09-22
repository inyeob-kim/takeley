"""Live demo: make one published Issue TRENDING via lifecycle signals.

Run:
  cd backend
  .\\.venv\\Scripts\\python.exe -m pytest tests/test_seed_one_trending_live.py -q -s

Uses real DB (SessionLocal). Sets recent follow + fresh velocity TRENDING path
so the home card shows 🔥 지금 뜨는.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import get_settings
from app.db.models import IssueFollow, MetricSnapshot, Signal
from app.db.session import SessionLocal, init_db
from app.pipeline.trend_status import (
    TREND_TRENDING,
    apply_trend_status,
    set_ai_trending_hint,
)
from app.pipeline.velocity import VelocityReading


SEED_USER = "trend-seed-user"


def test_seed_one_published_issue_trending_live():
    init_db()
    db = SessionLocal()
    cfg = get_settings()
    now = datetime.utcnow()
    try:
        signal = (
            db.query(Signal)
            .filter(Signal.status == "published")
            .order_by(Signal.published_at.desc().nullslast())
            .first()
        )
        assert signal is not None, "published Issue가 없습니다. 먼저 이슈를 배포하세요."

        # Recent internal: one follow inside window (IssueFollow row = personal; Trend uses created_at).
        follow = (
            db.query(IssueFollow)
            .filter(
                IssueFollow.user_id == SEED_USER,
                IssueFollow.signal_id == signal.id,
            )
            .first()
        )
        if follow is None:
            db.add(
                IssueFollow(
                    user_id=SEED_USER,
                    signal_id=signal.id,
                    created_at=now,
                )
            )
        else:
            follow.created_at = now

        # Fresh external evidence snapshot (likes OK — no reply threshold).
        db.add(
            MetricSnapshot(
                signal_id=signal.id,
                reply_count=2,
                like_count=40,
                retweet_count=5,
                quote_count=1,
                engagement_score=40 + 2 * 3 + 5 * 2 + 1 * 2.5,
                captured_at=now - timedelta(minutes=5),
            )
        )
        db.add(
            MetricSnapshot(
                signal_id=signal.id,
                reply_count=25,
                like_count=120,
                retweet_count=20,
                quote_count=4,
                engagement_score=120 + 25 * 3 + 20 * 2 + 4 * 2.5,
                captured_at=now,
            )
        )

        # Fresh AI hint (optional boost path); velocity alone is enough with reading below.
        set_ai_trending_hint(signal, True, when=now)

        db.commit()
        db.refresh(signal)

        # Explicit TRENDING velocity (above config thresholds) + recent internal → candidate TRENDING.
        reading = VelocityReading(
            reply_velocity=float(cfg.issue_trending_reply_velocity) + 5.0,
            engagement_velocity=float(cfg.issue_trending_engagement_velocity) + 20.0,
            trend_status=TREND_TRENDING,
        )
        # Clear prior status so upgrade is immediate from NORMAL.
        signal.trend_status = "NORMAL"
        signal.trend_status_updated_at = now - timedelta(hours=2)
        signal.is_trending = False
        db.commit()

        res = apply_trend_status(
            db, signal, velocity=reading, settings=cfg, now=now
        )
        db.commit()
        db.refresh(signal)

        print()
        print("seeded_issue_id=", signal.id)
        print("title=", signal.title)
        print("candidate=", res.candidate_status)
        print("final=", res.final_status)
        print("trend_status=", signal.trend_status)
        print("is_trending=", signal.is_trending)
        print("external=", res.external_level)
        print(
            "internal_recent_follow=",
            res.internal.recent_follow,
            "passed=",
            res.internal.passed,
        )

        assert res.candidate_status == TREND_TRENDING
        assert signal.trend_status == TREND_TRENDING
        assert signal.is_trending is True
    finally:
        db.close()
