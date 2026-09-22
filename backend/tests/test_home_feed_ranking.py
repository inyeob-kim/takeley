"""Home feed ranking: one trending pin, then published_at order."""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Signal
from app.db.session import Base
from app.services.issue_service import IssueService, order_home_feed


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _add_issue(
    db,
    *,
    title: str,
    category: str,
    trend_score: float,
    published_at: datetime,
    trend_status: str = "NORMAL",
    is_trending: bool = False,
) -> Signal:
    row = Signal(
        title=title,
        summary=f"{title} summary",
        why_it_matters="why",
        key_points=[],
        status="published",
        importance=0.5,
        confidence=0.5,
        trend_score=trend_score,
        trend_status=trend_status,
        is_trending=is_trending,
        category=category,
        topic="t",
        participation_suitable=True,
        participation_type="binary",
        participation_question="어떻게 보세요?",
        published_at=published_at,
        first_seen_at=published_at,
    )
    db.add(row)
    db.flush()
    return row


def test_order_home_feed_pins_top_trending():
    db = _session()
    now = datetime.utcnow()
    older = _add_issue(
        db,
        title="older high trend",
        category="기술",
        trend_score=0.9,
        published_at=now - timedelta(hours=5),
        trend_status="TRENDING",
        is_trending=True,
    )
    newer_low = _add_issue(
        db,
        title="newer low trend",
        category="기술",
        trend_score=0.1,
        published_at=now - timedelta(hours=1),
    )
    mid = _add_issue(
        db,
        title="mid",
        category="기술",
        trend_score=0.4,
        published_at=now - timedelta(hours=2),
    )
    db.commit()

    ordered = order_home_feed([older, newer_low, mid], limit=10)
    assert [r.title for r in ordered] == [
        "older high trend",
        "newer low trend",
        "mid",
    ]


def test_list_issues_all_pins_one_trending_then_published():
    db = _session()
    now = datetime.utcnow()
    _add_issue(
        db,
        title="hot-old",
        category="경제",
        trend_score=0.95,
        published_at=now - timedelta(days=2),
        trend_status="TRENDING",
        is_trending=True,
    )
    _add_issue(
        db,
        title="fresh",
        category="기술",
        trend_score=0.2,
        published_at=now - timedelta(hours=1),
    )
    _add_issue(
        db,
        title="yesterday",
        category="사회",
        trend_score=0.3,
        published_at=now - timedelta(days=1),
    )
    db.commit()

    listed = IssueService(db).list_issues(limit=10, sort="trending")
    titles = [i.title for i in listed.items]
    assert titles[0] == "hot-old"
    assert titles[1:] == ["fresh", "yesterday"]


def test_list_issues_industry_pins_within_category():
    db = _session()
    now = datetime.utcnow()
    _add_issue(
        db,
        title="global-hot",
        category="경제",
        trend_score=0.99,
        published_at=now - timedelta(days=3),
        trend_status="TRENDING",
        is_trending=True,
    )
    _add_issue(
        db,
        title="tech-hot",
        category="기술",
        trend_score=0.7,
        published_at=now - timedelta(days=2),
        trend_status="RISING",
    )
    _add_issue(
        db,
        title="tech-fresh",
        category="기술",
        trend_score=0.1,
        published_at=now - timedelta(hours=2),
    )
    _add_issue(
        db,
        title="tech-mid",
        category="기술",
        trend_score=0.2,
        published_at=now - timedelta(hours=5),
    )
    db.commit()

    tech = IssueService(db).list_issues(limit=10, sort="trending", category="기술")
    titles = [i.title for i in tech.items]
    assert titles[0] == "tech-hot"
    assert titles[1:] == ["tech-fresh", "tech-mid"]
    assert "global-hot" not in titles
