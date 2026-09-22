"""
Publish quota policy (Common Intelligence).

Concepts (env names kept for compatibility):

* DAILY_SIGNAL_CAP (`daily_signal_cap`)
  Soft daily pool for NORMAL publishes. Not an absolute hard block.

* PER_SYMBOL_DAILY_MIN (`per_symbol_daily_min`)
  Guarantee slots so a ticker is not starved when the soft pool is empty.
  Still subject to DAILY_SIGNAL_HARD_CEILING.

* BOOTSTRAP_PER_SYMBOL_MAX (`bootstrap_per_symbol_max`)
  Absolute max published-today count for a focus symbol that bootstrap
  may fill (via the bootstrap path) when the soft pool is empty.
  Re-running bootstrap cannot exceed this count for the day.

* DAILY_SIGNAL_HARD_CEILING (`daily_signal_hard_ceiling`)
  Absolute max published Signals per UTC day (all paths).
  Prevents O(watchlist) explosion from per-symbol mins.

Priority hook (uses existing `importance`, no new schema):
* If importance >= priority_importance_threshold and soft pool is empty,
  allow as `priority` until the hard ceiling — reserved for rare high-signal
  events. Set threshold > 1.0 to disable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishQuotaDecision:
    allowed: bool
    reason: str
    # global | min_slot | bootstrap | priority
    # denied_global_cap | denied_bootstrap_cap | denied_hard_ceiling


def decide_publish_quota(
    *,
    related_symbols: list[str],
    focus_symbols: set[str] | None,
    bootstrap: bool,
    global_quota_left: int,
    published_today_total: int,
    published_today_by_symbol: dict[str, int],
    per_symbol_daily_min: int,
    bootstrap_per_symbol_max: int,
    hard_ceiling: int,
    importance: float = 0.0,
    priority_importance_threshold: float = 0.85,
) -> PublishQuotaDecision:
    related = [s.upper() for s in (related_symbols or []) if s]
    focus = {s.upper() for s in (focus_symbols or set())}

    if hard_ceiling > 0 and published_today_total >= hard_ceiling:
        return PublishQuotaDecision(False, "denied_hard_ceiling")

    # 1) Per-symbol minimum guarantee (soft pool may already be empty).
    if related and per_symbol_daily_min > 0:
        for sym in related:
            if published_today_by_symbol.get(sym, 0) < per_symbol_daily_min:
                return PublishQuotaDecision(True, "min_slot")

    # 2) Bootstrap allowance for focus tickers only (absolute daily count).
    if bootstrap and focus and bootstrap_per_symbol_max > 0:
        overlapping = [s for s in related if s in focus]
        if not overlapping and not related:
            # Analyzer omitted tickers — still allow against focus once.
            overlapping = list(focus)
        for sym in overlapping:
            if published_today_by_symbol.get(sym, 0) < bootstrap_per_symbol_max:
                return PublishQuotaDecision(True, "bootstrap")
        if overlapping:
            return PublishQuotaDecision(False, "denied_bootstrap_cap")

    # 3) High-importance escape (optional; threshold > 1 disables).
    if (
        priority_importance_threshold <= 1.0
        and importance >= priority_importance_threshold
        and global_quota_left <= 0
    ):
        return PublishQuotaDecision(True, "priority")

    # 4) Soft global pool.
    if global_quota_left > 0:
        return PublishQuotaDecision(True, "global")

    return PublishQuotaDecision(False, "denied_global_cap")


def underserved_score(
    related_symbols: list[str],
    published_today_by_symbol: dict[str, int],
    per_symbol_daily_min: int,
) -> int:
    """Higher = more starved. Used to publish underserved tickers before others."""
    if per_symbol_daily_min <= 0:
        return 0
    related = [s.upper() for s in (related_symbols or []) if s]
    if not related:
        return 0
    return max(
        max(0, per_symbol_daily_min - published_today_by_symbol.get(sym, 0))
        for sym in related
    )


def expected_soft_bound(daily_signal_cap: int) -> int:
    return max(0, daily_signal_cap)


def expected_hard_bound(
    *,
    daily_signal_cap: int,
    per_symbol_daily_min: int,
    watchlist_size: int,
    hard_ceiling: int,
) -> int:
    """
    Operational bound for planning:
    soft pool + mins cannot exceed hard_ceiling.
    Theoretical mins alone are watchlist_size * per_symbol_daily_min,
    but hard_ceiling clamps the day.
    """
    soft = expected_soft_bound(daily_signal_cap)
    mins = max(0, watchlist_size) * max(0, per_symbol_daily_min)
    unbounded = max(soft, mins)  # illustrative; actual mix is more nuanced
    if hard_ceiling <= 0:
        return unbounded
    return min(unbounded, hard_ceiling) if unbounded else hard_ceiling
