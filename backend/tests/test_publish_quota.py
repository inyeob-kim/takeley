"""Publish quota policy edge cases (pure unit tests, no DB/LLM)."""

from app.pipeline.publish_quota import (
    decide_publish_quota,
    expected_hard_bound,
    underserved_score,
)


def _decide(**kwargs):
    base = dict(
        related_symbols=["AAA"],
        focus_symbols=None,
        bootstrap=False,
        global_quota_left=0,
        published_today_total=0,
        published_today_by_symbol={"AAA": 0},
        per_symbol_daily_min=2,
        bootstrap_per_symbol_max=3,
        hard_ceiling=30,
        importance=0.5,
        priority_importance_threshold=0.85,
    )
    base.update(kwargs)
    return decide_publish_quota(**base)


# --- Soft / hard / min / bootstrap ---


def test_min_slot_allows_when_global_cap_empty():
    d = _decide(global_quota_left=0, published_today_by_symbol={"AAA": 0})
    assert d.allowed and d.reason == "min_slot"


def test_global_cap_blocks_when_symbol_already_has_min():
    d = _decide(
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 2},
    )
    assert not d.allowed and d.reason == "denied_global_cap"


def test_bootstrap_allows_beyond_global_until_bootstrap_max():
    d = _decide(
        related_symbols=["AAA"],
        focus_symbols={"AAA"},
        bootstrap=True,
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 2},
    )
    assert d.allowed and d.reason == "bootstrap"

    denied = _decide(
        related_symbols=["AAA"],
        focus_symbols={"AAA"},
        bootstrap=True,
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 3},
    )
    assert not denied.allowed and denied.reason == "denied_bootstrap_cap"


def test_bootstrap_repeat_cannot_bypass_after_max():
    """Same focus symbol already at bootstrap max → no infinite bypass."""
    d = _decide(
        related_symbols=["AAA"],
        focus_symbols={"AAA"},
        bootstrap=True,
        global_quota_left=0,
        published_today_total=25,
        published_today_by_symbol={"AAA": 3},
        per_symbol_daily_min=2,
    )
    assert not d.allowed
    assert d.reason in {"denied_bootstrap_cap", "denied_global_cap"}


def test_global_pool_still_used_when_available():
    d = _decide(
        global_quota_left=4,
        published_today_by_symbol={"AAA": 5},
        published_today_total=5,
    )
    assert d.allowed and d.reason == "global"


def test_hard_ceiling_blocks_all_bypass_paths():
    d = _decide(
        global_quota_left=0,
        published_today_total=30,
        published_today_by_symbol={"AAA": 0},
        hard_ceiling=30,
        bootstrap=True,
        focus_symbols={"AAA"},
        importance=0.99,
    )
    assert not d.allowed and d.reason == "denied_hard_ceiling"


def test_watchlist_growth_bounded_by_hard_ceiling():
    """50 symbols × min=2 would be 100; hard ceiling clamps planning bound."""
    bound = expected_hard_bound(
        daily_signal_cap=10,
        per_symbol_daily_min=2,
        watchlist_size=50,
        hard_ceiling=30,
    )
    assert bound == 30


def test_remaining_zero_without_min_or_bootstrap_denies_normal():
    d = _decide(
        related_symbols=["AAA"],
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 2},
        bootstrap=False,
    )
    assert not d.allowed and d.reason == "denied_global_cap"


def test_three_symbols_min_slots_do_not_starve_later_tickers():
    """Each under-min symbol independently qualifies for min_slot."""
    for sym in ("AAA", "BBB", "CCC"):
        d = _decide(
            related_symbols=[sym],
            global_quota_left=0,
            published_today_total=10,
            published_today_by_symbol={"AAA": 0, "BBB": 0, "CCC": 0},
        )
        assert d.allowed and d.reason == "min_slot"


def test_underserved_score_prefers_starved_symbol():
    counts = {"AAA": 2, "BBB": 0}
    assert underserved_score(["BBB"], counts, 2) > underserved_score(
        ["AAA"], counts, 2
    )


def test_priority_importance_escape_when_soft_empty():
    d = _decide(
        related_symbols=["AAA"],
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 2},
        importance=0.9,
        priority_importance_threshold=0.85,
    )
    assert d.allowed and d.reason == "priority"


def test_priority_disabled_when_threshold_above_one():
    d = _decide(
        related_symbols=["AAA"],
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 2},
        importance=0.99,
        priority_importance_threshold=1.01,
    )
    assert not d.allowed and d.reason == "denied_global_cap"


def test_bootstrap_without_related_uses_focus():
    d = _decide(
        related_symbols=[],
        focus_symbols={"AAA"},
        bootstrap=True,
        global_quota_left=0,
        published_today_total=10,
        published_today_by_symbol={"AAA": 1},
    )
    assert d.allowed and d.reason == "bootstrap"
