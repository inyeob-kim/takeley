"""Deterministic pre-LLM junk filter (cheap gate)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_URL_RE = re.compile(r"https?://\S+", re.I)
_WHITESPACE_RE = re.compile(r"\s+")

# Engagement / promo noise (lowercase match).
_JUNK_MARKERS = (
    "follow me",
    "follow for",
    "subscribe",
    "giveaway",
    "retweet",
    "rt if",
    "like and",
    "click the link",
    "link in bio",
    "dm me",
    "airdrop",
    "nft drop",
    "promo code",
    "use code",
)

_MIN_CHARS = 40


@dataclass(frozen=True)
class CheapFilterDecision:
    accepted: bool
    reason: str


def _strip_urls(text: str) -> str:
    return _URL_RE.sub(" ", text or "")


def cheap_filter_text(text: str) -> CheapFilterDecision:
    """Return whether text is worth clustering / LLM analysis."""
    raw = (text or "").strip()
    if not raw:
        return CheapFilterDecision(False, "empty")

    without_urls = _WHITESPACE_RE.sub(" ", _strip_urls(raw)).strip()
    if len(without_urls) < _MIN_CHARS:
        # URL-only or tiny posts
        if _URL_RE.search(raw) and len(without_urls) < 12:
            return CheapFilterDecision(False, "url_only")
        return CheapFilterDecision(False, "too_short")

    lowered = without_urls.lower()
    for marker in _JUNK_MARKERS:
        if marker in lowered:
            return CheapFilterDecision(False, "engagement_junk")

    # Mostly non-letters (emoji spam, ticker spam without sentence)
    letters = sum(1 for c in without_urls if c.isalpha())
    if letters < max(12, int(len(without_urls) * 0.35)):
        return CheapFilterDecision(False, "low_signal_chars")

    return CheapFilterDecision(True, "ok")
