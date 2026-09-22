"""Lightweight cost / usage metering (call counts and size proxies)."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import UsageEvent

logger = logging.getLogger(__name__)

_usage_db: ContextVar[Session | None] = ContextVar("usage_db", default=None)

# Metric names (keep stable for rollups)
X_API_REQUESTS = "x_api_requests"
X_POSTS_RECEIVED = "x_posts_received"
X_SEARCH_REQUESTS = "x_search_requests"
RSS_REQUESTS = "rss_requests"
KR_RSS_REQUESTS = "kr_rss_requests"
DART_REQUESTS = "dart_requests"
ARTICLE_HTTP_REQUESTS = "article_http_requests"
CALENDAR_REQUESTS = "calendar_requests"
SYMBOL_SEARCH_REQUESTS = "symbol_search_requests"
LLM_CALLS = "llm_calls"
LLM_INPUT_TOKENS = "llm_input_tokens"
LLM_OUTPUT_TOKENS = "llm_output_tokens"
TTS_CHARACTERS = "tts_characters"
CHEAP_FILTER_DROPPED = "cheap_filter_dropped"
CANDIDATE_ACCEPTED = "candidate_accepted"
CANDIDATE_REJECTED = "candidate_rejected"
LLM_UNDERSTANDING = "llm_understanding"
UNDERSTANDING_REJECTED = "understanding_rejected"
LLM_MATCH = "llm_match"
ISSUE_CREATED = "issue_created"
ISSUE_UPDATED = "issue_updated"
ISSUE_REJECTED = "issue_rejected"
DUPLICATE_ISSUE_PREVENTED = "duplicate_issue_prevented"
ISSUE_PUBLISHED = "issue_published"

SCOPE_SHARED = "shared"
SCOPE_USER = "user"

# LLM stage → default scope (shared intelligence vs personalization)
_LLM_STAGE_SCOPE = {
    "analyze": SCOPE_SHARED,
    "understanding": SCOPE_SHARED,
    "match": SCOPE_SHARED,
    "quality_judge": SCOPE_SHARED,
    "select": SCOPE_USER,
    "synthesize": SCOPE_USER,
    "explain": SCOPE_USER,
}


def bind_usage_db(db: Session | None):
    """Bind a Session for subsequent record_usage calls in this context."""
    return _usage_db.set(db)


def reset_usage_db(token) -> None:
    _usage_db.reset(token)


def record_usage(
    metric: str,
    value: float = 1.0,
    *,
    tags: dict[str, Any] | None = None,
    scope_type: str | None = None,
    user_id: str | None = None,
    symbol: str | None = None,
    db: Session | None = None,
) -> None:
    """Persist one usage event. Uses bound db when db arg omitted."""
    session = db if db is not None else _usage_db.get()
    if session is None:
        logger.debug("usage skip metric=%s value=%s (no db)", metric, value)
        return
    merged = dict(tags or {})
    if scope_type:
        merged.setdefault("scope_type", scope_type)
    if user_id:
        merged.setdefault("user_id", user_id)
    if symbol:
        merged.setdefault("symbol", symbol.upper())
    try:
        session.add(
            UsageEvent(
                metric=metric,
                value=float(value),
                tags=merged,
            )
        )
        session.commit()
    except Exception:
        logger.exception("usage record failed metric=%s", metric)
        try:
            session.rollback()
        except Exception:
            pass


def record_llm_usage(
    resp,
    *,
    stage: str,
    model: str = "gpt-4o-mini",
    scope_type: str | None = None,
    user_id: str | None = None,
    symbol: str | None = None,
) -> None:
    scope = scope_type or _LLM_STAGE_SCOPE.get(stage, SCOPE_SHARED)
    base_tags: dict[str, Any] = {"stage": stage, "model": model}
    record_usage(
        LLM_CALLS,
        1,
        tags=base_tags,
        scope_type=scope,
        user_id=user_id,
        symbol=symbol,
    )
    usage = getattr(resp, "usage", None)
    if usage is None:
        return
    in_tok = getattr(usage, "prompt_tokens", None) or getattr(
        usage, "input_tokens", None
    )
    out_tok = getattr(usage, "completion_tokens", None) or getattr(
        usage, "output_tokens", None
    )
    if in_tok:
        record_usage(
            LLM_INPUT_TOKENS,
            float(in_tok),
            tags=base_tags,
            scope_type=scope,
            user_id=user_id,
            symbol=symbol,
        )
    if out_tok:
        record_usage(
            LLM_OUTPUT_TOKENS,
            float(out_tok),
            tags=base_tags,
            scope_type=scope,
            user_id=user_id,
            symbol=symbol,
        )


def rollup_since(db: Session, *, hours: int = 24) -> dict[str, float]:
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(UsageEvent.metric, UsageEvent.value)
        .filter(UsageEvent.created_at >= since)
        .all()
    )
    out: dict[str, float] = {}
    for metric, value in rows:
        out[metric] = out.get(metric, 0.0) + float(value or 0)
    return out


def log_rollup(db: Session, *, hours: int = 24) -> dict[str, float]:
    totals = rollup_since(db, hours=hours)
    logger.info("usage_rollup hours=%s totals=%s", hours, totals)
    return totals
