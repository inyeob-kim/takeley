"""Consumer list_issues content_kind filter (NEWS vs ISSUE)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Signal
from app.db.session import Base
from app.services.issue_service import IssueService


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _pub(db, *, title: str, kind: str, category: str = "기술") -> Signal:
    row = Signal(
        title=title,
        summary=f"{title} 요약입니다.",
        why_it_matters="",
        status="published",
        content_kind=kind,
        category=category,
        topic="t",
        published_at=datetime.utcnow(),
        first_seen_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_list_issues_defaults_to_issue_only():
    db = _session()
    _pub(db, title="이슈 카드 제목입니다", kind="ISSUE")
    _pub(db, title="뉴스 카드 제목입니다", kind="NEWS")
    listed = IssueService(db).list_issues(limit=10, sort="trending")
    assert listed.count == 1
    assert listed.items[0].content_kind == "ISSUE"
    assert listed.items[0].title.startswith("이슈")


def test_list_issues_news_filter():
    db = _session()
    _pub(db, title="이슈 카드 제목입니다", kind="ISSUE")
    _pub(db, title="뉴스 카드 제목입니다", kind="NEWS")
    news = IssueService(db).list_issues(
        limit=10, sort="new", content_kind="NEWS"
    )
    assert news.count == 1
    assert news.items[0].content_kind == "NEWS"


def test_list_issues_all_includes_both():
    db = _session()
    _pub(db, title="이슈 카드 제목입니다", kind="ISSUE")
    _pub(db, title="뉴스 카드 제목입니다", kind="NEWS")
    all_items = IssueService(db).list_issues(
        limit=10, sort="new", content_kind="ALL"
    )
    kinds = {i.content_kind for i in all_items.items}
    assert kinds == {"ISSUE", "NEWS"}


def test_news_detail_does_not_compose_column_from_rss_excerpt():
    """Detail used to dump Yahoo-related headlines into column_body for NEWS."""
    from app.db.models import RawItem, SignalSource

    db = _session()
    news = _pub(db, title="애플 스마트홈 허브 공개 예정", kind="NEWS")
    raw = RawItem(
        provider="news",
        external_id="rss-1",
        url="https://example.com/a",
        title="Apple stock pops - Yahoo Finance",
        text=(
            "Apple stock pops on report… Yahoo Finance "
            "Apple Is Finally Ready… Bloomberg.com "
            "Apple’s HomePad… 9to5Mac"
        ),
        author="rss",
        published_at=datetime.utcnow(),
        fetched_at=datetime.utcnow(),
        processed=True,
    )
    db.add(raw)
    db.flush()
    db.add(
        SignalSource(
            signal_id=news.id,
            raw_item_id=raw.id,
            provider="news",
            url=raw.url,
        )
    )
    db.commit()

    out = IssueService(db).get_issue(news.id)
    assert out is not None
    assert out.content_kind == "NEWS"
    assert out.column_body == ""
    assert "Yahoo Finance" not in out.column_body
    assert out.summary  # card summary still present


def test_news_detail_returns_stored_body():
    db = _session()
    news = _pub(db, title="그렉스 공장 폐쇄 계획 발표", kind="NEWS")
    news.column_body = (
        "영국 베이커리 체인 그렉스가 공장 네 곳을 닫고 인력을 줄이기로 했어요.\n\n"
        "본사 측은 매장 운영은 그대로 두고, 제조·물류를 재편한다고 밝혔어요."
    )
    db.commit()
    out = IssueService(db).get_issue(news.id)
    assert out is not None
    assert "공장 네 곳" in out.column_body
    assert "재편한다" in out.column_body
