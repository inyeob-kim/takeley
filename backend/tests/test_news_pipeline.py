"""NEWS / ISSUE / REJECT classification + NEWS guardrails."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Signal
from app.pipeline.news_generate import (
    NewsCard,
    apply_news_card_post_check,
    count_markdown_headings,
    generate_news_card,
    llm_payload_has_forbidden_keys,
    title_summary_token_coverage,
)
from app.pipeline.news_guardrails import news_passes_guardrails
from app.pipeline.prompts import NEWS_CARD_PROMPT_VERSION
from app.pipeline.understanding import (
    CONTENT_KIND_ISSUE,
    CONTENT_KIND_NEWS,
    CONTENT_KIND_REJECT,
    derive_is_issue_candidate,
    heuristic_understand,
    normalize_content_kind,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_normalize_content_kind():
    assert normalize_content_kind("news") == CONTENT_KIND_NEWS
    assert normalize_content_kind("ISSUE") == CONTENT_KIND_ISSUE
    assert normalize_content_kind("bogus") == CONTENT_KIND_REJECT


def test_is_issue_candidate_only_for_issue():
    assert derive_is_issue_candidate(CONTENT_KIND_ISSUE) is True
    assert derive_is_issue_candidate(CONTENT_KIND_NEWS) is False
    assert derive_is_issue_candidate(CONTENT_KIND_REJECT) is False


def test_heuristic_reject_opinion_not_news():
    u = heuristic_understand(
        text="I think NVIDIA will dominate AI forever and nothing else matters",
        provider="x",
    )
    assert u.content_kind == CONTENT_KIND_REJECT
    assert u.is_issue_candidate is False


def test_heuristic_reject_weather_advisory():
    u = heuristic_understand(
        text="10월 첫날, 기온 급락과 강한 바람 주의보가 발효됐습니다. 외출 시 주의하세요.",
        provider="news",
    )
    assert u.content_kind == CONTENT_KIND_REJECT
    assert u.reject_reason in ("low_surface_heuristic", "low_surface_value")
    assert u.surface_min < 0.55


def test_heuristic_reject_invite_app_update():
    u = heuristic_understand(
        text="애플 아이폰 초대장 앱 업데이트 소식 — 앱스토어에서 새 버전이 배포됐습니다.",
        provider="news",
    )
    assert u.content_kind == CONTENT_KIND_REJECT
    assert "low_surface" in (u.reject_reason or u.novelty)


def test_heuristic_reject_csat_award():
    u = heuristic_understand(
        text="현대백화점 고객만족도 9년 연속 1위 기록, 서비스 품질을 인정받았다.",
        provider="news",
    )
    assert u.content_kind == CONTENT_KIND_REJECT
    assert "low_surface" in (u.reject_reason or u.novelty)


def test_heuristic_keeps_dengue_despite_body_temperature_mention():
    """Body climate context must not trip 기온 pattern on the whole text."""
    u = heuristic_understand(
        text=(
            "플로리다 뎅기열, 감염자 수 증가 우려\n"
            "플로리다에서 뎅기열 환자가 늘고 있다. "
            "기온 상승과 더 많은 강수량은 모기 번식지를 늘릴 수 있다."
        ),
        provider="news",
    )
    assert u.content_kind != CONTENT_KIND_REJECT


def test_surface_gate_rejects_low_llm_scores():
    from app.pipeline.understanding import UnderstandingResult, apply_surface_gate

    u = UnderstandingResult(
        is_issue_candidate=False,
        relevance=0.4,
        hook=0.4,
        useful=0.5,
        takeley_fit=0.45,
        content_kind=CONTENT_KIND_NEWS,
        source="llm",
    )
    out = apply_surface_gate(u)
    assert out.content_kind == CONTENT_KIND_REJECT
    assert out.reject_reason == "low_surface_value"


def test_surface_gate_keeps_strong_scores():
    from app.pipeline.understanding import UnderstandingResult, apply_surface_gate

    u = UnderstandingResult(
        is_issue_candidate=False,
        relevance=0.8,
        hook=0.75,
        useful=0.7,
        takeley_fit=0.72,
        content_kind=CONTENT_KIND_NEWS,
        source="llm",
    )
    out = apply_surface_gate(u)
    assert out.content_kind == CONTENT_KIND_NEWS


def test_heuristic_reject_too_short():
    u = heuristic_understand(text="hi", provider="news")
    assert u.content_kind == CONTENT_KIND_REJECT
    assert u.is_issue_candidate is False


def test_heuristic_news_announcement():
    u = heuristic_understand(
        text="Apple announced a new iPhone launch date for September deliveries worldwide",
        provider="news",
    )
    assert u.content_kind == CONTENT_KIND_NEWS
    assert u.is_issue_candidate is False


def test_heuristic_sensitive_news_upgrades_to_issue():
    u = heuristic_understand(
        text="President announced new tariff policy affecting global trade routes",
        provider="news",
    )
    assert u.content_kind == CONTENT_KIND_ISSUE
    assert u.is_issue_candidate is True
    assert u.sensitive_review is True


def test_heuristic_debate_is_issue():
    u = heuristic_understand(
        text="Should cities ban gasoline cars by 2030? Public debate grows after new ruling",
        provider="x",
    )
    assert u.content_kind == CONTENT_KIND_ISSUE
    assert u.is_issue_candidate is True


def test_news_card_prompt_version_v5():
    assert NEWS_CARD_PROMPT_VERSION == "news_card_v5"


def test_title_summary_token_coverage_rejects_repeat():
    title = "삼성전자, AI칩 생산 확대"
    summary = "삼성전자가 AI칩 생산을 확대한다고 밝혔습니다."
    assert title_summary_token_coverage(title, summary) >= 0.55


def test_title_summary_token_coverage_allows_distinct():
    title = "미국 10년물 국채 수익률, 24년 만에 5.3% 돌파"
    summary = (
        "장기 금리 기준점으로 쓰이는 지표가 이전 고점을 넘어섰습니다. "
        "배경과 수준 변화가 핵심입니다."
    )
    assert title_summary_token_coverage(title, summary) < 0.55


def test_post_check_rejects_title_summary_overlap():
    body = "가" * 360
    card = NewsCard(
        title="삼성전자, AI칩 생산 확대",
        summary="삼성전자가 AI칩 생산을 확대한다고 밝혔습니다.",
        body=body,
        key_points=["사실 하나"],
        source="llm",
        ok=True,
    )
    out = apply_news_card_post_check(card)
    assert out.ok is False
    assert out.reason == "title_summary_overlap"


def test_post_check_rejects_too_many_headings():
    body = "## 하나\n\n" + ("내용입니다. " * 40) + "\n\n## 둘\n\n" + ("더 있습니다. " * 20)
    card = NewsCard(
        title="충분히 긴 뉴스 제목입니다",
        summary="제목과 다른 이유로 지금 열어볼 가치가 있습니다.",
        body=body,
        source="llm",
        ok=True,
    )
    assert count_markdown_headings(body) >= 2
    out = apply_news_card_post_check(card)
    assert out.ok is False
    assert out.reason == "too_many_headings"


def test_post_check_rejects_issue_style_cta():
    body = "가" * 360
    card = NewsCard(
        title="충분히 긴 뉴스 제목입니다",
        summary="여러분은 어떻게 생각하시나요? 지금 확인해 보세요.",
        body=body,
        source="llm",
        ok=True,
    )
    out = apply_news_card_post_check(card)
    assert out.ok is False
    assert out.reason == "issue_style_cta"


def test_post_check_accepts_valid_llm_card():
    body = (
        "원문에서 확인된 수치가 핵심입니다. 이전 고점을 넘어선 변화가 "
        "이번 브리핑의 중심이에요.\n\n"
        "해석이 있다면 주체를 밝혀 적습니다. 전망은 사실처럼 단정하지 않습니다.\n\n"
        "영향 범위는 출처에 나온 대상만 적습니다."
    )
    # pad to ≥350 without adding ##
    while len(body) < 360:
        body += " 구체 사실 문장을 이어 붙여 길이를 맞춥니다."
    card = NewsCard(
        title="미국 10년물 국채 수익률, 24년 만에 5.3% 돌파",
        summary="장기 금리 기준점이 한 단계 높아진 숫자입니다. 수준이 얼마나 유지되는지가 핵심이에요.",
        body=body,
        key_points=["10년물 5.3% 돌파", "24년 만의 수준"],
        category="금융",
        source="llm",
        ok=True,
    )
    out = apply_news_card_post_check(card)
    assert out.ok is True
    assert out.reason == ""


def test_forbidden_extra_keys_detected():
    assert llm_payload_has_forbidden_keys({"title": "a", "takeley_line": "x"}) == (
        "takeley_line"
    )
    assert llm_payload_has_forbidden_keys({"title": "a", "angle": "number_lead"}) == (
        "angle"
    )
    assert llm_payload_has_forbidden_keys({"title": "a", "summary": "b"}) is None


def test_news_generate_heuristic_ok():
    card = generate_news_card(
        text="Tesla reports record deliveries for Q3 after factory ramp.",
        provider="news",
        source_title="Tesla Q3 deliveries hit record",
        source_url="https://example.com/tesla",
    )
    assert card.ok
    assert len(card.title) >= 4
    assert len(card.summary) >= 8


def test_news_guardrails_require_url():
    db = _session()
    card = NewsCard(
        title="충분히 긴 뉴스 제목입니다",
        summary="충분히 긴 요약문입니다. 두 문장 이상이에요.",
        ok=True,
    )
    bad = news_passes_guardrails(
        db,
        card=card,
        source_url=None,
        provider="news",
        published_at=datetime.utcnow(),
        cluster_text="body",
    )
    assert bad.accepted is False
    assert bad.reason == "missing_source_url"


def test_news_guardrails_age():
    db = _session()
    card = NewsCard(
        title="충분히 긴 뉴스 제목입니다",
        summary="충분히 긴 요약문입니다. 두 문장 이상이에요.",
        ok=True,
    )
    old = datetime.utcnow() - timedelta(days=10)
    bad = news_passes_guardrails(
        db,
        card=card,
        source_url="https://example.com/a",
        provider="news",
        published_at=old,
        cluster_text="body",
    )
    assert bad.accepted is False
    assert bad.reason == "too_old"


def test_news_guardrails_pass():
    db = _session()
    card = NewsCard(
        title="충분히 긴 뉴스 제목입니다",
        summary="충분히 긴 요약문입니다. 두 문장 이상이에요.",
        ok=True,
    )
    ok = news_passes_guardrails(
        db,
        card=card,
        source_url="https://example.com/fresh-news",
        provider="news",
        published_at=datetime.utcnow() - timedelta(hours=2),
        cluster_text="body",
    )
    assert ok.accepted is True


def test_news_guardrails_duplicate_title():
    db = _session()
    title = "충분히 긴 뉴스 제목입니다"
    db.add(
        Signal(
            title=title,
            summary="기존에 저장된 요약문입니다.",
            status="draft",
            content_kind="NEWS",
        )
    )
    db.commit()
    card = NewsCard(
        title=title,
        summary="충분히 긴 요약문입니다. 두 문장 이상이에요.",
        ok=True,
    )
    bad = news_passes_guardrails(
        db,
        card=card,
        source_url="https://example.com/other",
        provider="news",
        published_at=datetime.utcnow(),
        cluster_text="body",
    )
    assert bad.accepted is False
    assert bad.reason == "duplicate_title"


def test_admin_draft_list_defaults_to_issue_only():
    from app.services.admin_issue_service import AdminIssueService

    db = _session()
    db.add(
        Signal(
            title="이슈 후보 제목입니다",
            summary="이슈 후보 요약문입니다.",
            status="draft",
            content_kind="ISSUE",
        )
    )
    db.add(
        Signal(
            title="뉴스 초안 제목입니다",
            summary="뉴스 초안 요약문입니다.",
            status="draft",
            content_kind="NEWS",
        )
    )
    db.commit()
    out = AdminIssueService(db).list_by_status(status="draft")
    assert out.count == 1
    assert out.items[0].content_kind == "ISSUE"
    all_out = AdminIssueService(db).list_by_status(
        status="draft", content_kind="ALL"
    )
    assert all_out.count == 2
    counts = AdminIssueService(db).counts()
    assert counts["draft"] == 1
    assert counts["news_draft"] == 1
    news_only = AdminIssueService(db).list_by_status(
        status="draft", content_kind="NEWS"
    )
    assert news_only.count == 1
    assert news_only.items[0].content_kind == "NEWS"
    assert "news_rejected" in counts


class _DripSettings:
    news_publish_interval_seconds = 900
    news_max_publish_per_cycle = 1
    news_auto_publish = True


def test_next_news_publish_at_staggers_fifteen_minutes():
    from worker.jobs.process_issues_v2 import _next_news_publish_at

    db = _session()
    settings = _DripSettings()
    first = _next_news_publish_at(db, settings)
    assert abs((first - datetime.utcnow()).total_seconds()) < 5

    db.add(
        Signal(
            title="뉴스 슬롯 A 제목입니다",
            summary="뉴스 슬롯 A 요약문입니다.",
            status="draft",
            content_kind="NEWS",
            scheduled_publish_at=first,
        )
    )
    db.commit()
    second = _next_news_publish_at(db, settings)
    assert abs((second - first).total_seconds() - 900) < 2

    db.add(
        Signal(
            title="뉴스 슬롯 B 제목입니다",
            summary="뉴스 슬롯 B 요약문입니다.",
            status="draft",
            content_kind="NEWS",
            scheduled_publish_at=second,
        )
    )
    db.commit()
    third = _next_news_publish_at(db, settings)
    assert abs((third - second).total_seconds() - 900) < 2


def test_publish_due_caps_news_to_one_per_cycle(monkeypatch):
    from app.core import config as config_mod
    from app.services.admin_issue_service import AdminIssueService

    db = _session()
    now = datetime.utcnow()
    for i in range(3):
        db.add(
            Signal(
                title=f"뉴스 drip {i} 제목입니다 충분히 김",
                summary=f"뉴스 drip {i} 요약문입니다.",
                status="draft",
                content_kind="NEWS",
                lifecycle="CANDIDATE",
                scheduled_publish_at=now - timedelta(minutes=5 - i),
            )
        )
    db.add(
        Signal(
            title="이슈 예약 제목입니다 충분히 김",
            summary="이슈 예약 요약문입니다.",
            status="draft",
            content_kind="ISSUE",
            lifecycle="CANDIDATE",
            scheduled_publish_at=now - timedelta(minutes=1),
        )
    )
    db.commit()

    class _Settings:
        news_max_publish_per_cycle = 1
        news_publish_interval_seconds = 900

    monkeypatch.setattr(config_mod, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        "app.services.push_enqueue_service.enqueue_news_new",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.push_enqueue_service.enqueue_signal_new",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.push_send_service.send_pending_pushes",
        lambda *a, **k: 0,
    )

    svc = AdminIssueService(db)
    n = svc.publish_due(now=now)
    # 1 ISSUE + 1 NEWS (cap)
    assert n == 2
    published = db.query(Signal).filter(Signal.status == "published").all()
    assert len(published) == 2
    assert sum(1 for r in published if r.content_kind == "NEWS") == 1
    assert sum(1 for r in published if r.content_kind == "ISSUE") == 1
    still_draft_news = (
        db.query(Signal)
        .filter(Signal.status == "draft", Signal.content_kind == "NEWS")
        .count()
    )
    assert still_draft_news == 2

    n2 = svc.publish_due(now=now)
    assert n2 == 1
    assert (
        db.query(Signal)
        .filter(Signal.status == "published", Signal.content_kind == "NEWS")
        .count()
        == 2
    )
