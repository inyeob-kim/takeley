"""Official site pages stay on existing Issue and /i/{id} data."""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import IssueTake, ParticipationOption, Signal, User
from app.db.session import Base, get_db
from app.main import app


def _client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    def _override():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    signal = Signal(
        title="엔비디아 수요 이슈",
        summary="데이터센터 투자가 이어지고 있어요.",
        why_it_matters="반도체 수요가 다시 중요해졌어요.",
        column_body="반도체 수요가 다시 살아나고 있습니다. AI 인프라 투자가 핵심입니다. " * 3,
        column_author_name="Takeley",
        status="published",
        published_at=datetime.utcnow(),
        category="경제",
        participation_suitable=True,
        participation_question="수요가 더 갈까요?",
        image_url="/media/issue-images/cover.png",
    )
    session.add(signal)
    session.flush()
    session.add(ParticipationOption(signal_id=signal.id, label="더 간다", display_order=0))
    session.add(ParticipationOption(signal_id=signal.id, label="숨 고른다", display_order=1))
    author = User(display_name="김에디터", device_id="writer-1")
    session.add(author)
    session.flush()
    session.add(
        IssueTake(
            issue_id=signal.id,
            author_id=author.id,
            title="수요가 오래갈까",
            body="확인된 사실은 투자 계획입니다.\n\n해석은 아직 갈립니다.",
            status="published",
            published_at=datetime.utcnow(),
        )
    )
    session.commit()
    return TestClient(app), signal.id


def test_missing_cover_is_logo_on_home_list_only():
    client, _issue_id = _client()
    try:
        session = next(app.dependency_overrides[get_db]())
        blank = Signal(
            title="이미지 없는 이슈",
            summary="대표 이미지가 없습니다.",
            status="published",
            published_at=datetime.utcnow(),
            category="경제",
        )
        session.add(blank)
        session.commit()
        blank_id = blank.id
        home = client.get("/")
        assert home.status_code == 200
        assert 'class="is-logo"' in home.text
        detail = client.get(f"/issues/{blank_id}")
        assert detail.status_code == 200
        assert "이미지 없는 이슈" in detail.text
        assert 'class="is-logo"' not in detail.text
        listed = client.get("/issues")
        assert 'class="is-logo"' in listed.text
        assert "/static/og-splash.png" in listed.text
    finally:
        app.dependency_overrides.clear()


def test_home_lists_issue_and_column():
    client, issue_id = _client()
    try:
        page = client.get("/")
        assert page.status_code == 200
        body = page.text
        assert "엔비디아 수요 이슈" in body
        assert f"/issues/{issue_id}" in body
        assert f"/i/{issue_id}" not in body
        assert "칼럼" in body
        assert "수요가 오래갈까" in body
        columns = client.get("/columns")
        assert columns.status_code == 200
        assert "엔비디아 수요 이슈" in columns.text
        assert 'rel="canonical"' in body
        assert "og:title" in body
        assert 'class="app-qr"' in body
        assert "모바일 앱 받기" in body
        assert "https://apps.apple.com/kr/app/takeley/id6815212932" in body
        assert "/static/app-qr.svg" in body
        assert "min-width: 1320px" in body
    finally:
        app.dependency_overrides.clear()


def test_issue_filter_and_take_page_keep_share_path():
    client, issue_id = _client()
    try:
        listed = client.get("/issues", params={"category": "경제"})
        assert listed.status_code == 200
        assert "엔비디아 수요 이슈" in listed.text
        other = client.get("/issues", params={"category": "스포츠"})
        assert "엔비디아 수요 이슈" not in other.text
        home_link = client.get("/")
        take_href = "/columns/"
        assert take_href in home_link.text
        take_id = home_link.text.split("/columns/")[1].split('"')[0]
        detail = client.get(f"/columns/{take_id}")
        assert detail.status_code == 200
        assert "수요가 오래갈까" in detail.text
        assert f"/issues/{issue_id}" in detail.text
        article = client.get(f"/issues/{issue_id}")
        assert article.status_code == 200
        assert "엔비디아 수요 이슈" in article.text
        assert 'id="take"' in article.text
        assert "댓글은 모바일 앱에서 남길 수 있어요." in article.text
        assert "https://apps.apple.com/kr/app/takeley/id6815212932" in article.text
        assert "js-vote" in article.text
        share = client.get(f"/i/{issue_id}")
        assert share.status_code == 200
        assert "js-vote" in share.text or "생각" in share.text
        assert 'class="app-qr"' not in share.text
    finally:
        app.dependency_overrides.clear()
