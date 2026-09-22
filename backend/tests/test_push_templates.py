from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.services.push_template_service import (
    ensure_default_templates,
    render_push_copy,
    render_template,
    update_template,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_ensure_default_templates_seeds_builtin_rows():
    db = _session()
    n = ensure_default_templates(db)
    assert n == 2
    assert ensure_default_templates(db) == 0


def test_render_template_placeholders():
    assert (
        render_template("안녕 {title} / {symbols}", {"title": "MU", "symbols": "MU"})
        == "안녕 MU / MU"
    )


def test_render_push_copy_uses_db_template():
    db = _session()
    ensure_default_templates(db)
    update_template(
        db,
        "signal_new",
        title_template="새 이슈 ({title})",
        body_template="{body}",
    )
    title, body = render_push_copy(
        db,
        "signal_new",
        {
            "title": "테스트",
            "body": "확인해보세요.",
            "summary": "",
            "symbols": "",
            "signal_id": "sig-1",
            "brief_date": "",
        },
    )
    assert title == "새 이슈 (테스트)"
    assert body == "확인해보세요."


def test_signal_template_uses_title_body():
    db = _session()
    ensure_default_templates(db)
    title, body = render_push_copy(
        db,
        "signal_new",
        {
            "title": "마이크론 성장",
            "body": "새롭게 나온 내용을 확인해보세요.",
            "summary": "수요가 늘고 있어요.",
            "symbols": "MU",
            "signal_id": "sig-1",
            "brief_date": "",
        },
    )
    assert title == "마이크론 성장"
    assert body == "새롭게 나온 내용을 확인해보세요."
    assert "수요가" not in body
