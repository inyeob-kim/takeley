"""Unit tests for re-engagement push copy (no summary dump)."""

from types import SimpleNamespace

from app.services.push_copy import (
    PUSH_BODY_MAX,
    PUSH_KIND_GENERAL,
    PUSH_KIND_PARTICIPATION,
    PUSH_KIND_TREND,
    PUSH_TITLE_MAX,
    build_signal_new_copy,
    clip_push_text,
    resolve_push_kind,
)


def _src(**kwargs):
    base = dict(
        id="issue-1",
        title="빅테크 경쟁, 시장 점유율로 판가름 날까?",
        participation_suitable=False,
        participation_question=None,
        trend_status="NORMAL",
        is_trending=False,
        push_title=None,
        push_body=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_clip_push_text_boundary_and_mixed_scripts():
    assert clip_push_text("  hello   world  ", 20) == "hello world"
    long_ko = "가" * 50
    clipped = clip_push_text(long_ko, 10)
    assert clipped.endswith("…")
    assert len(clipped) == 10
    mixed = "OpenAI 실적 발표 EPS +12% — 시장 반응은?"
    out = clip_push_text(mixed, 24)
    assert len(out) <= 24
    assert "…" in out or len(mixed) <= 24


def test_resolve_kind_priority_participation_over_trend():
    assert (
        resolve_push_kind(
            participation_suitable=True,
            trend_status="TRENDING",
            is_trending=True,
        )
        == PUSH_KIND_PARTICIPATION
    )
    assert (
        resolve_push_kind(
            participation_suitable=False,
            trend_status="RISING",
        )
        == PUSH_KIND_TREND
    )
    assert (
        resolve_push_kind(
            participation_suitable=False,
            trend_status="NORMAL",
        )
        == PUSH_KIND_GENERAL
    )


def test_participation_uses_real_question():
    copy = build_signal_new_copy(
        _src(
            participation_suitable=True,
            participation_question="점유율이 승부를 가른다에 동의하나요?",
        )
    )
    assert copy.kind == PUSH_KIND_PARTICIPATION
    assert "동의" in copy.body
    assert "갈리고" not in copy.body


def test_participation_fallback_variant_when_no_question():
    copy = build_signal_new_copy(_src(participation_suitable=True))
    assert copy.kind == PUSH_KIND_PARTICIPATION
    assert copy.body in (
        "당신은 어떻게 생각하나요?",
        "이 이슈, 어떻게 보세요?",
    )


def test_trend_and_general_bodies_are_cta_not_summary():
    summary_leak = "최근 빅테크 기업들 간의 경쟁이 치열해지고 있어요."
    trend = build_signal_new_copy(
        _src(title="AI 안경 시장", trend_status="TRENDING")
    )
    assert trend.kind == PUSH_KIND_TREND
    assert summary_leak not in trend.body
    assert "확인" in trend.body

    general = build_signal_new_copy(_src(title="OpenAI 업데이트"))
    assert general.kind == PUSH_KIND_GENERAL
    assert summary_leak not in general.body
    assert "확인" in general.body


def test_override_wins():
    copy = build_signal_new_copy(
        _src(
            push_title="직접 쓴 제목",
            push_body="직접 쓴 본문입니다",
            participation_suitable=True,
            participation_question="무시될 질문?",
        )
    )
    assert copy.title == "직접 쓴 제목"
    assert copy.body == "직접 쓴 본문입니다"


def test_title_truncated_to_limit():
    copy = build_signal_new_copy(_src(title="가" * 80))
    assert len(copy.title) <= PUSH_TITLE_MAX
    assert copy.title.endswith("…")
    assert len(copy.body) <= PUSH_BODY_MAX
