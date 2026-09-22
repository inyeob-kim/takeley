"""Push copy presentation — re-engagement CTAs, not Issue summary dumps."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

PUSH_TITLE_MAX = 40
PUSH_BODY_MAX = 72

PUSH_KIND_PARTICIPATION = "participation"
PUSH_KIND_TREND = "trend"
PUSH_KIND_GENERAL = "general"

_PARTICIPATION_VARIANTS = (
    "당신은 어떻게 생각하나요?",
    "이 이슈, 어떻게 보세요?",
)
_TREND_VARIANTS = (
    "지금 왜 관심이 커지고 있는지 확인해보세요.",
    "무슨 변화가 있는지 확인해보세요.",
)
_GENERAL_VARIANTS = (
    "새롭게 나온 내용을 확인해보세요.",
    "이번 변화가 무엇인지 확인해보세요.",
)

_BREAK_CHARS = set(" \t\n\r,./;:!?…·—–-，。、！？")


class PushCopySource(Protocol):
    id: str
    title: str | None
    participation_suitable: bool | None
    participation_question: str | None
    trend_status: str | None
    is_trending: bool | None
    push_title: str | None
    push_body: str | None


@dataclass(frozen=True)
class PushCopy:
    title: str
    body: str
    kind: str


def clip_push_text(text: str | None, max_len: int) -> str:
    """Collapse whitespace and truncate on a natural boundary (Unicode code points)."""
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_len:
        return cleaned
    if max_len <= 1:
        return "…"
    budget = max_len - 1
    window = cleaned[:budget]
    cut = -1
    for i, ch in enumerate(window):
        if ch in _BREAK_CHARS:
            cut = i
    if cut >= max(8, budget // 3):
        out = window[:cut].rstrip(" \t,./;:!?·—–-")
    else:
        out = window.rstrip()
    if not out:
        out = cleaned[:budget]
    return f"{out}…"


def resolve_push_kind(
    *,
    participation_suitable: bool | None,
    trend_status: str | None,
    is_trending: bool | None = None,
) -> str:
    if bool(participation_suitable):
        return PUSH_KIND_PARTICIPATION
    status = (trend_status or "").strip().upper()
    if status in {"RISING", "TRENDING"} or bool(is_trending):
        return PUSH_KIND_TREND
    return PUSH_KIND_GENERAL


def _pick_variant(signal_id: str, variants: tuple[str, ...]) -> str:
    digest = hashlib.sha256((signal_id or "").encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(variants)
    return variants[idx]


def _body_for_kind(kind: str, signal_id: str, question: str | None) -> str:
    if kind == PUSH_KIND_PARTICIPATION:
        q = " ".join((question or "").split()).strip()
        if q:
            return clip_push_text(q, PUSH_BODY_MAX)
        return _pick_variant(signal_id, _PARTICIPATION_VARIANTS)
    if kind == PUSH_KIND_TREND:
        return _pick_variant(signal_id, _TREND_VARIANTS)
    return _pick_variant(signal_id, _GENERAL_VARIANTS)


def build_signal_new_copy(source: PushCopySource) -> PushCopy:
    """
    Build re-engagement push title/body from Issue metadata.
    Never uses summary / why_it_matters / key_points.
    Admin push_title / push_body override when non-empty.
    """
    signal_id = getattr(source, "id", "") or ""
    kind = resolve_push_kind(
        participation_suitable=getattr(source, "participation_suitable", False),
        trend_status=getattr(source, "trend_status", None),
        is_trending=getattr(source, "is_trending", False),
    )

    override_title = " ".join(
        (getattr(source, "push_title", None) or "").split()
    ).strip()
    override_body = " ".join(
        (getattr(source, "push_body", None) or "").split()
    ).strip()

    if override_title or override_body:
        title = clip_push_text(
            override_title or (getattr(source, "title", None) or ""),
            PUSH_TITLE_MAX,
        ) or "TAKELEY"
        body = clip_push_text(
            override_body or _body_for_kind(
                kind, signal_id, getattr(source, "participation_question", None)
            ),
            PUSH_BODY_MAX,
        ) or _pick_variant(signal_id, _GENERAL_VARIANTS)
        return PushCopy(title=title, body=body, kind=kind)

    title = clip_push_text(getattr(source, "title", None), PUSH_TITLE_MAX) or "TAKELEY"
    body = _body_for_kind(
        kind, signal_id, getattr(source, "participation_question", None)
    )
    if not body:
        body = _pick_variant(signal_id, _GENERAL_VARIANTS)
    return PushCopy(title=title, body=body, kind=kind)
