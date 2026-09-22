"""TAKELEY trend status: current interest state (transient), not lifetime popularity.

Pipeline:
  External + Internal signals
    → calculate_candidate_status()   # signal-only; ignores current status
    → apply_trend_state_transition() # upgrade fast / downgrade with grace
    → Final trend_status

SSOT: issues.trend_status in {NORMAL, RISING, TRENDING}.
is_trending syncs as (trend_status == TRENDING) for API compat.

IssueFollow rows are personal interest (persistent). Trend internal only
counts recent follows via created_at window — never expire/delete Follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import IssueFollow, IssueView, Participation, Signal
from app.pipeline.velocity import (
    VelocityReading,
    compute_velocity,
    latest_snapshots,
    snapshot_has_activity,
    snapshots_show_activity_delta,
)

TREND_NORMAL = "NORMAL"
TREND_RISING = "RISING"
TREND_TRENDING = "TRENDING"

_STATUS_RANK = {
    TREND_NORMAL: 0,
    TREND_RISING: 1,
    TREND_TRENDING: 2,
}

_STEP_DOWN = {
    TREND_TRENDING: TREND_RISING,
    TREND_RISING: TREND_NORMAL,
    TREND_NORMAL: TREND_NORMAL,
}


@dataclass(frozen=True)
class InternalInterest:
    """Recent (windowed) TAKELEY interest — not lifetime Follow/open totals."""

    unique_openers: int  # recent unique openers (last_seen_at in window)
    follow_count: int  # recent follows by IssueFollow.created_at (row kept forever)
    participation_count: int  # recent votes
    passed: bool
    # Explicit recent channels (for gating / future weighting).
    recent_open: int = 0
    recent_follow: int = 0
    recent_vote: int = 0


@dataclass(frozen=True)
class TrendResolution:
    external_level: str
    internal: InternalInterest
    candidate_status: str
    final_status: str


def _normalize_status(value: str | None) -> str:
    text = (value or TREND_NORMAL).upper()
    if text in _STATUS_RANK:
        return text
    return TREND_NORMAL


def _status_rank(value: str | None) -> int:
    return _STATUS_RANK[_normalize_status(value)]


def _window_cutoff(cfg: Settings, *, now: datetime) -> datetime:
    hours = float(cfg.issue_trend_internal_window_hours)
    return now - timedelta(hours=hours)


def measure_recent_internal_interest(
    db: Session,
    signal_id: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> InternalInterest:
    """Windowed internal signals. Does not mutate IssueFollow / IssueView rows.

    Channels are computed independently so Follow can later be weighted/excluded
    without rewriting open/vote logic.
    """
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    cutoff = _window_cutoff(cfg, now=when)

    recent_open = int(
        db.query(func.count(IssueView.id))
        .filter(
            IssueView.signal_id == signal_id,
            IssueView.last_seen_at >= cutoff,
        )
        .scalar()
        or 0
    )
    # Personal Follow persists forever; Trend only counts recent create time.
    recent_follow = int(
        db.query(func.count(IssueFollow.id))
        .filter(
            IssueFollow.signal_id == signal_id,
            IssueFollow.created_at >= cutoff,
        )
        .scalar()
        or 0
    )
    recent_vote = int(
        db.query(func.count(Participation.id))
        .filter(
            Participation.signal_id == signal_id,
            or_(
                Participation.created_at >= cutoff,
                Participation.updated_at >= cutoff,
            ),
        )
        .scalar()
        or 0
    )

    passed = (
        recent_open >= int(cfg.issue_trend_min_unique_opens)
        or recent_follow >= int(cfg.issue_trend_min_follows)
        or recent_vote >= int(cfg.issue_trend_min_participations)
    )
    return InternalInterest(
        unique_openers=recent_open,
        follow_count=recent_follow,
        participation_count=recent_vote,
        passed=passed,
        recent_open=recent_open,
        recent_follow=recent_follow,
        recent_vote=recent_vote,
    )


def measure_internal_interest(
    db: Session,
    signal_id: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> InternalInterest:
    """Back-compat alias → recent (windowed) internal interest."""
    return measure_recent_internal_interest(
        db, signal_id, settings=settings, now=now
    )


def _ai_trending_hint(signal: Signal) -> bool:
    emph = getattr(signal, "emphasis", None) or {}
    if isinstance(emph, dict):
        return bool(emph.get("ai_trending"))
    return False


def _parse_ai_trending_at(signal: Signal) -> datetime | None:
    emph = getattr(signal, "emphasis", None) or {}
    if not isinstance(emph, dict):
        return None
    raw = emph.get("ai_trending_at")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        # Store/compare as naive UTC iso strings.
        cleaned = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def set_ai_trending_hint(
    signal: Signal,
    ai_trending: bool,
    *,
    when: datetime | None = None,
) -> None:
    """Persist AI scale judgment + freshness timestamp in emphasis JSON."""
    emph = dict(getattr(signal, "emphasis", None) or {})
    if ai_trending:
        emph["ai_trending"] = True
        emph["ai_trending_at"] = (when or datetime.utcnow()).isoformat()
    else:
        emph["ai_trending"] = False
        emph["ai_trending_at"] = None
    signal.emphasis = emph


def ai_hint_is_fresh(
    signal: Signal,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> bool:
    """True only when ai_trending is set and ai_trending_at is within window."""
    if not _ai_trending_hint(signal):
        return False
    stamped = _parse_ai_trending_at(signal)
    if stamped is None:
        # Legacy True without timestamp → treat as stale (no permanent pin).
        return False
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    return stamped >= _window_cutoff(cfg, now=when)


def has_fresh_external_evidence(
    db: Session,
    signal_id: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> bool:
    """Fresh MetricSnapshot in window with observable external activity.

    Does NOT require reply_count >= a fixed threshold (comments are not mandatory).
    reply_count=0 alone does not fail if other engagement fields or a positive
    inter-snapshot delta show activity.
    """
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    cutoff = _window_cutoff(cfg, now=when)
    snaps = latest_snapshots(db, signal_id, limit=2)
    if not snaps:
        return False
    latest = snaps[-1]
    if latest.captured_at is None or latest.captured_at < cutoff:
        return False
    if snapshot_has_activity(latest):
        return True
    if len(snaps) >= 2 and snapshots_show_activity_delta(snaps[-2], snaps[-1]):
        return True
    return False


def velocity_status_for_candidate(
    db: Session,
    signal_id: str,
    *,
    velocity: VelocityReading | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> str:
    """Velocity bucket with stale-snapshot guard (no threshold number changes).

    If the caller passes a VelocityReading (e.g. right after recording a snapshot),
    use it unless the latest snapshot is outside the freshness window.
    """
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    cutoff = _window_cutoff(cfg, now=when)
    snaps = latest_snapshots(db, signal_id, limit=1)
    if snaps and (snaps[-1].captured_at is None or snaps[-1].captured_at < cutoff):
        return TREND_NORMAL
    if velocity is not None:
        return _normalize_status(velocity.trend_status)
    if not snaps:
        return TREND_NORMAL
    reading = compute_velocity(db, signal_id)
    return _normalize_status(reading.trend_status)


def external_level_from_inputs(
    *,
    velocity_status: str,
    fresh_ai_path: bool = False,
    # Legacy kwargs kept so older call sites/tests do not break at import time.
    ai_trending: bool = False,
    reply_peak: int = 0,
    min_reply_count: int = 0,
) -> str:
    """Map velocity OR fresh AI path into an external bucket (no internal gate).

    Velocity thresholds are applied upstream; this only merges paths.
    Does not use reply_count / source_reply_peak as a new AI gate.
    """
    del ai_trending, reply_peak, min_reply_count  # unused — product: no reply threshold
    vel = _normalize_status(velocity_status)
    if vel == TREND_TRENDING:
        return TREND_TRENDING
    if fresh_ai_path:
        return TREND_TRENDING
    if vel == TREND_RISING:
        return TREND_RISING
    return TREND_NORMAL


def combine_trend_status(external_level: str, internal_passed: bool) -> str:
    """External fame alone never becomes RISING/TRENDING without internal interest."""
    if not internal_passed:
        return TREND_NORMAL
    level = _normalize_status(external_level)
    if level == TREND_TRENDING:
        return TREND_TRENDING
    if level == TREND_RISING:
        return TREND_RISING
    return TREND_NORMAL


def calculate_candidate_status(
    db: Session,
    signal: Signal,
    *,
    velocity: VelocityReading | None = None,
    ai_trending: bool | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> TrendResolution:
    """Signal-only candidate. Must not consult current trend_status for the result."""
    cfg = settings or get_settings()
    when = now or datetime.utcnow()

    if ai_trending is not None:
        # Caller override (tests / apply_issue_fields).
        if ai_trending:
            if not _parse_ai_trending_at(signal) or not _ai_trending_hint(signal):
                set_ai_trending_hint(signal, True, when=when)
        else:
            set_ai_trending_hint(signal, False)

    vel_status = velocity_status_for_candidate(
        db, signal.id, velocity=velocity, settings=cfg, now=when
    )
    fresh_ai = ai_hint_is_fresh(signal, settings=cfg, now=when) and has_fresh_external_evidence(
        db, signal.id, settings=cfg, now=when
    )
    external = external_level_from_inputs(
        velocity_status=vel_status,
        fresh_ai_path=fresh_ai,
    )
    internal = measure_recent_internal_interest(
        db, signal.id, settings=cfg, now=when
    )
    candidate = combine_trend_status(external, internal.passed)
    return TrendResolution(
        external_level=external,
        internal=internal,
        candidate_status=candidate,
        final_status=candidate,
    )


def apply_trend_state_transition(
    current_status: str,
    candidate_status: str,
    *,
    status_updated_at: datetime | None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> str:
    """Compare current vs candidate; upgrade immediate, downgrade one step after grace."""
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    current = _normalize_status(current_status)
    candidate = _normalize_status(candidate_status)

    if _status_rank(candidate) > _status_rank(current):
        return candidate
    if candidate == current:
        return current

    # Downgrade — time-based grace only (no strikes column).
    grace = timedelta(minutes=float(cfg.issue_trend_downgrade_grace_minutes))
    if status_updated_at is None:
        # Legacy rows: allow one-step decay on first lifecycle refresh.
        grace_elapsed = True
    else:
        grace_elapsed = (when - status_updated_at) >= grace
    if not grace_elapsed:
        return current
    return _STEP_DOWN[current]


def resolve_trend_status(
    db: Session,
    signal: Signal,
    *,
    velocity: VelocityReading | None = None,
    ai_trending: bool | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> TrendResolution:
    """Candidate + transition preview (does not write). Prefer apply_trend_status to persist."""
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    measured = calculate_candidate_status(
        db,
        signal,
        velocity=velocity,
        ai_trending=ai_trending,
        settings=cfg,
        now=when,
    )
    final = apply_trend_state_transition(
        getattr(signal, "trend_status", None) or TREND_NORMAL,
        measured.candidate_status,
        status_updated_at=getattr(signal, "trend_status_updated_at", None),
        settings=cfg,
        now=when,
    )
    return TrendResolution(
        external_level=measured.external_level,
        internal=measured.internal,
        candidate_status=measured.candidate_status,
        final_status=final,
    )


def apply_trend_status(
    db: Session,
    signal: Signal,
    *,
    velocity: VelocityReading | None = None,
    ai_trending: bool | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> TrendResolution:
    """Sole writer for trend_status / is_trending (lifecycle authority)."""
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    resolution = resolve_trend_status(
        db,
        signal,
        velocity=velocity,
        ai_trending=ai_trending,
        settings=cfg,
        now=when,
    )
    previous = _normalize_status(getattr(signal, "trend_status", None))
    final = resolution.final_status
    signal.trend_status = final
    if final != previous:
        signal.trend_status_updated_at = when
    signal.is_trending = final == TREND_TRENDING
    return resolution


def refresh_published_trend_statuses(
    db: Session,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> int:
    """Recompute trend for published Issues so status can decay without new raw.

    Correctness-first: walk all published rows. Batch/priority can be added later
    without changing this call site.
    """
    cfg = settings or get_settings()
    when = now or datetime.utcnow()
    rows = db.query(Signal).filter(Signal.status == "published").all()
    for signal in rows:
        apply_trend_status(db, signal, settings=cfg, now=when)
    db.commit()
    return len(rows)
