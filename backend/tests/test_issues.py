"""Issue API + participation basics."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import ParticipationOption, Signal
from app.db.session import Base
from app.services.issue_service import IssueService, replace_participation_options


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_issue_list_and_participate():
    db = _session()
    signal = Signal(
        title="엔비디아 수요 이슈",
        summary="데이터센터 투자가 이어지고 있어요.",
        why_it_matters="AI 관련 관심이 커요.",
        key_points=["수요", "공급"],
        status="published",
        importance=0.8,
        confidence=0.7,
        trend_score=0.75,
        category="Technology",
        topic="nvidia",
        participation_suitable=True,
        participation_type="binary",
        participation_question="수요가 계속 강할까요?",
        published_at=datetime.utcnow(),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    replace_participation_options(db, signal, ["계속 강할 것 같다", "둔화될 것 같다"])
    db.commit()

    svc = IssueService(db)
    listed = svc.list_issues(limit=10, sort="trending")
    assert listed.count == 1
    assert listed.items[0].participation_suitable is True
    assert len(listed.items[0].options) == 2

    by_cat = svc.list_issues(limit=10, category="기술")
    assert by_cat.count == 1
    by_legacy = svc.list_issues(limit=10, category="Tech")
    assert by_legacy.count == 1
    by_q = svc.list_issues(limit=10, q="엔비디아")
    assert by_q.count == 1
    miss = svc.list_issues(limit=10, q="없는검색어xyz")
    assert miss.count == 0

    opt = listed.items[0].options[0]
    result = svc.participate(signal.id, user_id="u1", option_id=opt.id)
    assert result is not None
    assert result["participation_count"] == 1
    assert result["my_option_id"] == opt.id

    again = svc.participate(signal.id, user_id="u1", option_id=listed.items[0].options[1].id)
    assert again["participation_count"] == 1
    assert again["my_option_id"] == opt.id

    detail = svc.get_issue(signal.id, user_id="u1")
    assert detail is not None
    assert detail.my_option_id == opt.id
    assert detail.content_updated_at == signal.content_updated_at

    comment = svc.add_comment(signal.id, user_id="u1", content="실적이 중요해요")
    assert comment is not None
    comments = svc.list_comments(signal.id)
    assert len(comments) == 1

    ev = svc.record_event(signal.id, "open")
    assert ev["open_count"] == 1
