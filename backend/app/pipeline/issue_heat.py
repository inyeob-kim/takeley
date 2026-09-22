"""Engagement heat for Issue topic ingest — replies/metrics only, no keyword trending."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeatDecision:
    accepted: bool
    reason: str
    score: float
    reply_count: int


def reply_count(metrics: dict | None) -> int:
    if not metrics:
        return 0
    return int(metrics.get("reply_count") or 0)


def engagement_score(metrics: dict | None) -> float:
    """Weighted X public_metrics → heat score (replies weighted highest)."""
    if not metrics:
        return 0.0
    likes = float(metrics.get("like_count") or 0)
    replies = float(metrics.get("reply_count") or 0)
    rts = float(metrics.get("retweet_count") or 0)
    quotes = float(metrics.get("quote_count") or 0)
    return likes + replies * 3.0 + rts * 2.0 + quotes * 2.5


def topic_heat_decision(
    *,
    metrics: dict | None,
    min_score: float,
    min_replies: int,
) -> HeatDecision:
    """
    Keep posts that already have discussion volume.
    Trending is NOT keyword-based — only engagement thresholds here.
    AI decides is_trending later in analyze.
    """
    score = engagement_score(metrics)
    replies = reply_count(metrics)

    if replies >= min_replies and score >= min_score:
        return HeatDecision(True, "hot_replies", score, replies)
    if replies >= min_replies:
        # Enough conversation even if likes are modest
        return HeatDecision(True, "reply_threshold", score, replies)
    if score >= min_score * 1.5 and replies >= max(1, min_replies // 2):
        return HeatDecision(True, "hot_engagement", score, replies)
    return HeatDecision(False, "cold_engagement", score, replies)


def pick_hottest(
    items: list,
    *,
    limit: int,
    min_score: float,
    min_replies: int,
) -> list:
    """Sort by reply/engagement desc, keep those that clear heat gate, cap count."""
    scored: list[tuple[float, int, object]] = []
    for item in items:
        payload = getattr(item, "raw_payload", None) or {}
        metrics = payload.get("public_metrics") or payload.get("metrics")
        metrics_dict = metrics if isinstance(metrics, dict) else None
        decision = topic_heat_decision(
            metrics=metrics_dict,
            min_score=min_score,
            min_replies=min_replies,
        )
        if decision.accepted:
            scored.append((decision.score, decision.reply_count, item))
    scored.sort(key=lambda x: (x[1], x[0]), reverse=True)
    return [item for _, _, item in scored[:limit]]


def max_reply_count_from_payloads(payloads: list[dict | None]) -> int:
    peak = 0
    for payload in payloads:
        if not payload:
            continue
        metrics = payload.get("public_metrics") or payload.get("metrics")
        if isinstance(metrics, dict):
            peak = max(peak, reply_count(metrics))
    return peak
