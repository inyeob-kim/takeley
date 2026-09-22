"""Dynamic X search queries derived from recent Understanding topics (Phase B light)."""

from __future__ import annotations

import logging
import re

from app.db.repositories import CursorRepository

logger = logging.getLogger(__name__)

_CURSOR_PROVIDER = "x"
_CURSOR_KEY = "dynamic:topics"
_MAX_TOPICS = 12


def _sanitize_topic(topic: str) -> str | None:
    t = re.sub(r"[^\w\s\-\.]", " ", (topic or "").strip())
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < 4:
        return None
    # X query: quote multi-word
    parts = t.split()[:6]
    if len(parts) == 1:
        return f"{parts[0]} lang:en -is:retweet"
    return f"\"{' '.join(parts)}\" lang:en -is:retweet"


def remember_topics(cursor_repo: CursorRepository, topics: list[str]) -> None:
    existing_raw = cursor_repo.get(_CURSOR_PROVIDER, _CURSOR_KEY) or ""
    existing = [p for p in existing_raw.split("|") if p.strip()]
    for topic in topics:
        clean = (topic or "").strip()[:80]
        if not clean:
            continue
        if clean not in existing:
            existing.insert(0, clean)
    existing = existing[:_MAX_TOPICS]
    cursor_repo.set(_CURSOR_PROVIDER, _CURSOR_KEY, "|".join(existing))


def dynamic_search_queries(
    cursor_repo: CursorRepository, *, budget: int = 2
) -> list[str]:
    """Build up to `budget` recent-search queries from remembered topics."""
    raw = cursor_repo.get(_CURSOR_PROVIDER, _CURSOR_KEY) or ""
    topics = [p for p in raw.split("|") if p.strip()]
    out: list[str] = []
    for topic in topics:
        q = _sanitize_topic(topic)
        if q and q not in out:
            out.append(q)
        if len(out) >= max(0, budget):
            break
    return out
