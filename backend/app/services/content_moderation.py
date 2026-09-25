"""Lightweight objectionable-content filter for user posts."""

from __future__ import annotations

# Product constraint: Apple 1.2 requires a filter. Keep this list narrow so
# debate language still ships; slurs / sexual / violent abuse are blocked.
_BLOCKED_NEEDLES = (
    "씨발",
    "시발",
    "좆",
    "병신",
    "지랄",
    "꺼져",
    "강간",
    "소아성",
    "아동포르",
    "child porn",
    "childporn",
    "csam",
    "nigger",
    "faggot",
    "rape",
    "kill yourself",
    "자살해",
)


class ObjectionableContent(ValueError):
    def __init__(self) -> None:
        super().__init__("objectionable_content")


def contains_objectionable(text: str | None) -> bool:
    raw = (text or "").strip().lower()
    if not raw:
        return False
    compact = raw.replace(" ", "")
    return any(needle in raw or needle.replace(" ", "") in compact for needle in _BLOCKED_NEEDLES)


def reject_objectionable(*parts: str | None) -> None:
    if any(contains_objectionable(part) for part in parts):
        raise ObjectionableContent()
