"""TAKELEY columnist roster — distinct from Contributor."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Issue
from app.db.session import Base
from app.services.columnist_service import ColumnistError, ColumnistService


def test_columnist_profile_lists_published_issues():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    service = ColumnistService(db)
    created = service.create(
        display_name="김칼럼",
        headline="테이클리 선정",
        bio="국제정치를 씁니다.",
        specialties=["국제정치", "외교"],
    )
    issue = Issue(
        title="테스트 이슈 제목입니다",
        summary="요약 텍스트가 충분히 깁니다.",
        why_it_matters="",
        status="published",
    )
    db.add(issue)
    db.commit()
    service.apply_to_issue(issue, created.id)
    db.commit()

    profile = service.public_profile(created.id)
    assert profile.display_name == "김칼럼"
    assert profile.headline == "테이클리 선정"
    assert profile.specialties == ["국제정치", "외교"]
    assert profile.email is None
    assert len(profile.issues) == 1
    assert profile.issue_count == 1
    assert profile.issues[0].id == issue.id
    assert issue.column_author_name == "김칼럼"

    extra = [
        Issue(
            title=f"추가 칼럼 제목 {i}",
            summary="요약 텍스트가 충분히 깁니다.",
            why_it_matters="",
            status="published",
        )
        for i in range(12)
    ]
    db.add_all(extra)
    db.commit()
    for row in extra:
        service.apply_to_issue(row, created.id)
    db.commit()
    paged = service.public_profile(created.id)
    assert paged.issue_count == 13
    assert len(paged.issues) == 10
    more = service.public_issues(created.id, limit=10, offset=10)
    assert more.count == 13
    assert len(more.items) == 3


def test_columnist_email_public_only_when_shown():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    service = ColumnistService(db)
    created = service.create(
        display_name="이필진",
        contact_email="writer@takeley.co",
        show_email=False,
    )
    hidden = service.public_profile(created.id)
    assert hidden.email is None
    service.update(created.id, show_email=True)
    shown = service.public_profile(created.id)
    assert shown.email == "writer@takeley.co"
    try:
        service.update(created.id, contact_email="not-an-email")
        raised = False
    except ColumnistError as exc:
        raised = True
        assert "invalid_contact_email" in str(exc)
    assert raised


def test_private_profile_is_hidden_from_app():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    service = ColumnistService(db)
    created = service.create(
        display_name="비공개 칼럼",
        profile_public=False,
    )
    issue = Issue(
        title="배포된 칼럼 제목입니다",
        summary="요약 텍스트가 충분히 깁니다.",
        why_it_matters="",
        status="published",
    )
    db.add(issue)
    db.commit()
    service.apply_to_issue(issue, created.id)
    db.commit()

    try:
        service.public_profile(created.id)
        raised = False
    except ColumnistError as exc:
        raised = True
        assert exc.status_code == 404
    assert raised

    try:
        service.public_issues(created.id)
        issues_raised = False
    except ColumnistError as exc:
        issues_raised = True
        assert exc.status_code == 404
    assert issues_raised

    from app.services.issue_service import _to_issue_out

    public = _to_issue_out(db, issue)
    assert public.column_author_name == "비공개 칼럼"
    assert public.columnist_id is None

    admin = _to_issue_out(db, issue, keep_columnist_link=True)
    assert admin.columnist_id == created.id

    service.update(created.id, profile_public=True)
    visible = service.public_profile(created.id)
    assert visible.display_name == "비공개 칼럼"
    opened = _to_issue_out(db, issue)
    assert opened.columnist_id == created.id
