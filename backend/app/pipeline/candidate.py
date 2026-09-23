"""Candidate pool — priority for LLM budget, NOT Issue meaning.

Engagement / replies / keywords must never hard-reject Issue creation here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class CandidateDecision:
    accepted_into_pool: bool
    priority_score: float
    reasons: tuple[str, ...] = ()


@dataclass
class ScoredCandidate:
    raw_id: str
    text: str
    url: str | None
    provider: str
    published_at: datetime | None
    payload: dict
    priority_score: float
    reasons: list[str] = field(default_factory=list)


def _provider_prior(provider: str) -> float:
    p = (provider or "").lower()
    if p in ("official", "sec", "ir"):
        return 1.0
    if p == "news":
        return 0.85
    if p == "x":
        return 0.55
    if p == "reddit":
        return 0.4
    return 0.5


def _recency_factor(published_at: datetime | None, *, now: datetime | None = None) -> float:
    if published_at is None:
        return 0.35
    now = now or datetime.now(timezone.utc)
    pub = published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_h = max(0.0, (now - pub).total_seconds() / 3600.0)
    # ~1.0 within 6h, ~0.5 at 48h, asymptote toward 0.15
    return max(0.15, math.exp(-age_h / 36.0))


def _engagement_from_payload(payload: dict | None) -> tuple[float, int]:
    if not payload:
        return 0.0, 0
    metrics = payload.get("public_metrics") or payload.get("metrics") or {}
    if not isinstance(metrics, dict):
        return 0.0, 0
    likes = float(metrics.get("like_count") or 0)
    replies = int(metrics.get("reply_count") or 0)
    rts = float(metrics.get("retweet_count") or 0)
    quotes = float(metrics.get("quote_count") or 0)
    eng = likes + replies * 3.0 + rts * 2.0 + quotes * 2.5
    return eng, replies


def priority_score(
    *,
    provider: str,
    published_at: datetime | None,
    payload: dict | None,
    now: datetime | None = None,
) -> CandidateDecision:
    """Score for LLM ordering only — never blocks Issue creation."""
    eng, replies = _engagement_from_payload(payload)
    rec = _recency_factor(published_at, now=now)
    prior = _provider_prior(provider)
    score = (
        0.45 * rec
        + 0.25 * prior
        + 0.20 * min(1.0, math.log1p(eng) / 8.0)
        + 0.10 * min(1.0, replies / 20.0)
    )
    reasons = ["recency", "provider_prior", "engagement_log"]
    # Always accept into pool consideration; caller applies Top-N budget.
    return CandidateDecision(True, round(score, 4), tuple(reasons))


def rank_for_pool(
    items: list[ScoredCandidate],
    *,
    budget: int,
) -> list[ScoredCandidate]:
    """Return top-N by priority. Does not drop low-engagement as meaning reject."""
    budget = max(1, budget)
    ordered = sorted(items, key=lambda c: c.priority_score, reverse=True)
    return ordered[:budget]


def rank_for_pool_reserved(
    items: list[ScoredCandidate],
    *,
    budget: int,
) -> list[ScoredCandidate]:
    """Keep the best post of each industry, then fill the rest by score.

    Industries with no posts are skipped. This does not reject by keyword.
    """
    budget = max(1, budget)
    ordered = sorted(items, key=lambda c: c.priority_score, reverse=True)
    picked: list[ScoredCandidate] = []
    seen: set[str] = set()
    best_by_industry: dict[str, ScoredCandidate] = {}
    for candidate in ordered:
        industry = str((candidate.payload or {}).get("issue_industry") or "")
        if industry and industry not in best_by_industry:
            best_by_industry[industry] = candidate
    for candidate in best_by_industry.values():
        if len(picked) >= budget:
            break
        picked.append(candidate)
        seen.add(candidate.raw_id)
    for candidate in ordered:
        if len(picked) >= budget:
            break
        if candidate.raw_id in seen:
            continue
        picked.append(candidate)
        seen.add(candidate.raw_id)
    return picked
