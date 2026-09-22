"""Deterministic Issue quality gate (no second LLM judge)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import MarketSignal, SignalStatus


@dataclass(frozen=True)
class IssueQualityDecision:
    accepted: bool
    reason: str
    signal: MarketSignal


def passes_issue_quality_gate(
    signal: MarketSignal,
    *,
    source_count: int,
) -> IssueQualityDecision:
    title = (signal.title or "").strip()
    summary = (signal.summary or "").strip()
    if len(title) < 4:
        signal.status = SignalStatus.REJECTED
        return IssueQualityDecision(False, "title_too_short", signal)
    if len(title) > 200:
        signal.title = title[:200]
    if len(summary) < 8:
        signal.status = SignalStatus.REJECTED
        return IssueQualityDecision(False, "summary_too_short", signal)
    if source_count < 1 and not (signal.source_urls or signal.providers):
        signal.status = SignalStatus.REJECTED
        return IssueQualityDecision(False, "no_evidence", signal)
    if signal.participation_suitable:
        opts = [o for o in (signal.participation_options or []) if str(o).strip()]
        if len(opts) < 2:
            # Downgrade to read-only rather than reject the Issue.
            signal.participation_suitable = False
            signal.participation_type = None
            signal.participation_question = None
            signal.participation_options = []
    signal.status = SignalStatus.DRAFT
    return IssueQualityDecision(True, "ok", signal)
