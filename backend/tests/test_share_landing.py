"""Share landing OG HTML + share analytics events."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import IssueUserEvent, ParticipationOption, Signal
from app.db.session import Base, get_db
from app.main import app
from app.services.issue_service import IssueService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_share_landing_readable_content_and_cta(monkeypatch):
    db = _session()
    signal = Signal(
        title="엔비디아 수요 이슈",
        summary="데이터센터 투자가 이어지고 있어요.",
        column_body=(
            "반도체 수요가 다시 살아나고 있습니다.\n\n"
            "특히 AI 인프라 투자가 핵심입니다."
        ),
        status="published",
        published_at=datetime.utcnow(),
        category="경제",
        participation_suitable=True,
        participation_question="수요가 더 갈까요?",
        open_count=42,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    db.add_all(
        [
            ParticipationOption(
                signal_id=signal.id, label="더 간다", display_order=0
            ),
            ParticipationOption(
                signal_id=signal.id, label="꺾인다", display_order=1
            ),
        ]
    )
    db.commit()

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    from app.core import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("PUBLIC_SHARE_ORIGIN", "http://testserver")
    monkeypatch.setenv(
        "PUBLIC_ANDROID_STORE_URL",
        "https://play.google.com/store/apps/details?id=com.takeley.app",
    )
    monkeypatch.setenv("PUBLIC_IOS_STORE_URL", "https://apps.apple.com/app/id000")
    cfg.get_settings.cache_clear()

    client = TestClient(app)
    res = client.get(f"/i/{signal.id}?sid=abc&ref=u1")
    assert res.status_code == 200
    body = res.text
    assert "og:title" in body
    assert "엔비디아 수요 이슈" in body
    assert "데이터센터 투자가 이어지고 있어요." in body
    assert "반도체 수요가 다시 살아나고 있습니다." in body
    assert "특히 AI 인프라 투자가 핵심입니다." in body
    assert "다른 사람 생각" in body
    assert "수요가 더 갈까요?" in body
    assert "더 간다" in body
    assert "꺾인다" in body
    assert "??" in body
    assert "내 생각 남기고, 남들 분포도 앱에서 보기" in body
    assert "42명이 봤어요" in body
    # Must not leak real vote percentages / bar widths in the teaser block.
    teaser_block = body.split("teaser-opts")[1].split("teaser-lock")[0]
    assert 'style="width:' not in teaser_block
    assert ">0%<" not in teaser_block
    assert ">50%<" not in teaser_block
    assert "이 이슈, 어떻게 생각해?" in body
    assert "결과는 앱에서 확인할 수 있어요" not in body
    assert "명이 생각을 남겼어요" not in body
    assert "topbar" in body
    assert "border-bottom" in body
    assert f"takeley://i/{signal.id}" in body
    assert "sid=abc" in body
    assert "ref=u1" in body
    assert "웹으로 계속 읽기" not in body
    assert "http-equiv=\"refresh\"" not in body.lower()
    assert "location.replace" not in body
    assert "play.google.com" in body

    missing = client.get("/i/does-not-exist")
    assert missing.status_code == 404

    app.dependency_overrides.clear()
    cfg.get_settings.cache_clear()


def test_record_share_events_with_attribution():
    db = _session()
    signal = Signal(
        title="공유 테스트",
        summary="요약",
        status="published",
        published_at=datetime.utcnow(),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    svc = IssueService(db)
    out = svc.record_event(
        signal.id,
        "share_clicked",
        user_id="u-share",
        share_id="sid-1",
        ref_user_id="u-inviter",
        share_intent="ask",
    )
    assert out is not None
    assert out["ok"] is True

    row = (
        db.query(IssueUserEvent)
        .filter(
            IssueUserEvent.signal_id == signal.id,
            IssueUserEvent.event == "share_clicked",
        )
        .one()
    )
    assert row.share_id == "sid-1"
    assert row.ref_user_id == "u-inviter"
    assert row.share_intent == "ask"

    opened = svc.record_event(
        signal.id,
        "shared_link_opened",
        user_id="u-guest",
        share_id="sid-1",
        ref_user_id="u-inviter",
    )
    assert opened["ok"] is True
