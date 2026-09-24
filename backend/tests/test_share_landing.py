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
    assert "선택한 뒤에 다른 사람 생각을 볼 수 있어요." in body
    assert "결과 보기" in body
    assert "js-confirm-vote" in body
    assert "data-option-id=" in body
    assert body.index('id="teaser"') < body.index("반도체 수요가 다시 살아나고 있습니다.")
    assert "42명이 봤어요" in body
    # Must not leak real vote percentages / bar widths in the teaser block.
    teaser_block = body.split("teaser-opts")[1].split("teaser-lock")[0]
    assert 'style="width:' not in teaser_block
    assert ">0%<" not in teaser_block
    assert ">50%<" not in teaser_block
    assert "이 이슈, 너는 어떻게 생각해?" in body
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
    assert 'class="cover"' not in body
    assert "og-default.png" in body
    assert "나는 ‘더 간다’에 한 표" not in body

    voted = client.get(f"/i/{signal.id}?take=%EB%8D%94+%EA%B0%84%EB%8B%A4")
    assert voted.status_code == 200
    assert "나는 ‘더 간다’에 한 표 했어" in voted.text
    assert 'class="cover"' not in voted.text

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
        share_intent="issue_only",
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
    assert row.share_intent == "issue_only"

    opened = svc.record_event(
        signal.id,
        "shared_link_opened",
        user_id="u-guest",
        share_id="sid-1",
        ref_user_id="u-inviter",
    )
    assert opened["ok"] is True


def test_web_participate_does_not_use_demo_user():
    db = _session()
    signal = Signal(
        title="웹 투표",
        summary="요약",
        status="published",
        published_at=datetime.utcnow(),
        participation_suitable=True,
        participation_question="어느 쪽?",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    opt = ParticipationOption(signal_id=signal.id, label="이쪽", display_order=0)
    db.add(opt)
    db.commit()
    db.refresh(opt)

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)
    registered = client.post(
        "/api/v1/devices/register",
        json={"device_id": "web-device-123456", "platform": "web"},
    )
    assert registered.status_code == 200
    user_id = registered.json()["user"]["id"]
    assert user_id != "demo-user"

    voted = client.post(
        f"/api/v1/issues/{signal.id}/participate",
        json={"option_id": opt.id, "user_id": user_id},
    )
    assert voted.status_code == 200
    body = voted.json()
    assert body["my_option_id"] == opt.id
    assert body["options"][0]["count"] == 1

    again = client.post(
        f"/api/v1/issues/{signal.id}/participate",
        json={"option_id": opt.id, "user_id": user_id},
    )
    assert again.status_code == 200
    assert again.json()["participation_count"] == 1

    other = ParticipationOption(signal_id=signal.id, label="저쪽", display_order=1)
    db.add(other)
    db.commit()
    db.refresh(other)
    switched = client.post(
        f"/api/v1/issues/{signal.id}/participate",
        json={"option_id": other.id, "user_id": user_id},
    )
    assert switched.status_code == 200
    switched_body = switched.json()
    assert switched_body["my_option_id"] == opt.id
    assert switched_body["participation_count"] == 1

    from app.db.models import Participation

    rows = db.query(Participation).filter(Participation.signal_id == signal.id).all()
    assert len(rows) == 1
    assert rows[0].user_id == user_id
    assert rows[0].option_id == opt.id

    app.dependency_overrides.clear()
