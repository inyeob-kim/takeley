"""Judgment note + distribution gate + other-take scoring."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models import Base, Issue, Participation, ParticipationOption, UserPreference
from app.services.issue_service import IssueService
from app.services.other_take_service import compute_split, pick_other_take


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _issue_with_options(db, *, n_votes: int = 0):
    issue = Issue(
        title="테스트 이슈 제목입니다",
        summary="테스트 요약문입니다.",
        status="published",
        participation_suitable=True,
        participation_question="어떻게 생각하세요?",
        participation_type="binary",
        published_at=datetime.utcnow(),
    )
    db.add(issue)
    db.flush()
    o1 = ParticipationOption(signal_id=issue.id, label="찬성", display_order=0)
    o2 = ParticipationOption(signal_id=issue.id, label="반대", display_order=1)
    db.add_all([o1, o2])
    db.flush()
    for i in range(n_votes):
        opt = o1 if i % 2 == 0 else o2
        db.add(
            Participation(
                signal_id=issue.id,
                user_id=f"u-seed-{i}",
                option_id=opt.id,
                note=f"시드 투표 이유입니다 {i:02d} 충분히 길게",
            )
        )
    db.commit()
    return issue, o1, o2


def _patch_settings(monkeypatch, **kwargs):
    settings = get_settings()
    for key, value in kwargs.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(
        "app.pipeline.trend_status.apply_trend_status",
        lambda *a, **k: None,
    )


def test_participate_stores_note_and_allows_change(monkeypatch):
    db = _session()
    issue, o1, o2 = _issue_with_options(db)
    _patch_settings(
        monkeypatch,
        distribution_min_responses=30,
        allow_position_change=True,
        judgment_note_max_chars=120,
    )
    svc = IssueService(db)
    first = svc.participate(
        issue.id, user_id="u1", option_id=o1.id, note="첫 한 줄 TAKE 입니다."
    )
    assert first is not None
    assert first["my_option_id"] == o1.id
    assert first["my_note"] == "첫 한 줄 TAKE 입니다."
    assert first["position_changed"] is False

    changed = svc.participate(
        issue.id, user_id="u1", option_id=o2.id, note="바꾼 이유입니다."
    )
    assert changed is not None
    assert changed["my_option_id"] == o2.id
    assert changed["position_changed"] is True
    assert changed["my_note"] == "바꾼 이유입니다."


def test_distribution_hidden_until_min_responses(monkeypatch):
    db = _session()
    issue, o1, o2 = _issue_with_options(db, n_votes=5)
    _patch_settings(monkeypatch, distribution_min_responses=30)
    svc = IssueService(db)
    out = svc.participate(issue.id, user_id="viewer", option_id=o1.id)
    assert out is not None
    assert out["distribution_visible"] is False
    assert all(o.count == 0 for o in out["options"])


def test_distribution_visible_when_enough_votes(monkeypatch):
    db = _session()
    issue, o1, o2 = _issue_with_options(db, n_votes=30)
    _patch_settings(monkeypatch, distribution_min_responses=30)
    svc = IssueService(db)
    out = svc.participate(issue.id, user_id="viewer", option_id=o1.id)
    assert out is not None
    assert out["distribution_visible"] is True
    assert sum(o.count for o in out["options"]) >= 30


def test_compute_split_balanced():
    assert abs(compute_split({"a": 50, "b": 50}, "a") - 0.5) < 1e-6
    assert abs(compute_split({"a": 90, "b": 10}, "a") - 0.1) < 1e-6


def test_other_take_returns_note_when_gates_pass(monkeypatch):
    db = _session()
    issue, o1, o2 = _issue_with_options(db, n_votes=40)
    _patch_settings(
        monkeypatch,
        distribution_min_responses=30,
        other_take_min_responses=30,
        other_take_split_hide_below=0.0,
        other_take_session_idle_minutes=15,
        other_take_daily_cap=2,
        other_take_same_side_every_n=5,
        other_take_skip_rate_block=0.80,
        allow_position_change=True,
    )
    prefs = UserPreference(user_id="viewer", participation_experiment_bucket="B")
    db.add(prefs)
    db.commit()

    IssueService(db).participate(issue.id, user_id="viewer", option_id=o1.id)
    card = pick_other_take(db, issue_id=issue.id, user_id="viewer")
    assert card is not None
    assert card["note"]
    assert card["exposure_id"]


def test_other_take_bucket_a_skips(monkeypatch):
    db = _session()
    issue, o1, o2 = _issue_with_options(db, n_votes=40)
    _patch_settings(
        monkeypatch,
        other_take_min_responses=30,
        other_take_split_hide_below=0.0,
        other_take_session_idle_minutes=15,
        other_take_daily_cap=2,
        other_take_same_side_every_n=5,
        other_take_skip_rate_block=0.80,
        distribution_min_responses=30,
        allow_position_change=True,
    )
    db.add(UserPreference(user_id="viewer", participation_experiment_bucket="A"))
    db.commit()
    IssueService(db).participate(issue.id, user_id="viewer", option_id=o1.id)
    assert pick_other_take(db, issue_id=issue.id, user_id="viewer") is None
