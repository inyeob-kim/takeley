"""Golden A–E semantic match + candidate priority tests (no live OpenAI)."""

from __future__ import annotations

from app.pipeline.candidate import priority_score, rank_for_pool, ScoredCandidate
from app.pipeline.evidence import trust_tier_for_provider
from app.pipeline.industries import discovery_query_for, industry_x_queries
from app.pipeline.issue_quality import passes_issue_quality_gate
from app.pipeline.matching import (
    DECISION_NEW,
    DECISION_REJECT,
    DECISION_UPDATE,
    ExistingIssueBrief,
    heuristic_match,
)
from app.pipeline.understanding import heuristic_understand
from app.domain.models import MarketSignal


def test_discovery_query_omits_has_replies():
    q = discovery_query_for("ai")
    assert q is not None
    assert "has:replies" not in q
    legacy = industry_x_queries(("ai",), split_replies=False)[0][1]
    assert "has:replies" in legacy
    broad = industry_x_queries(("ai",), split_replies=True)[0][1]
    assert "has:replies" not in broad
    ko = discovery_query_for("ai", "korea")
    assert ko is not None
    assert "lang:ko" in ko
    assert "has:replies" not in ko


def test_build_topic_lanes_used_for_ingest_shape():
    from app.pipeline.industries import build_topic_lanes, select_topic_lanes

    lanes = build_topic_lanes(("ai", "tech"))
    assert len(lanes) == 4
    selected, nxt = select_topic_lanes(lanes, budget=8, offset=0)
    assert len(selected) == 4  # budget capped to pool size
    assert nxt == 0


def test_candidate_priority_does_not_hard_reject_low_engagement():
    d = priority_score(
        provider="x",
        published_at=None,
        payload={"public_metrics": {"reply_count": 0, "like_count": 0}},
    )
    assert d.accepted_into_pool is True
    assert d.priority_score >= 0


def test_rank_for_pool_caps_budget():
    items = [
        ScoredCandidate("1", "a", None, "x", None, {}, 0.9),
        ScoredCandidate("2", "b", None, "x", None, {}, 0.1),
        ScoredCandidate("3", "c", None, "news", None, {}, 0.5),
    ]
    top = rank_for_pool(items, budget=2)
    assert len(top) == 2
    assert top[0].raw_id == "1"


def test_golden_a_same_event_paraphrases_update():
    """Case A: same Blackwell delay story → UPDATE."""
    existing = [
        ExistingIssueBrief(
            id="iss-1",
            title="NVIDIA delays Blackwell shipment",
            summary="NVIDIA delayed Blackwell GPU shipments to customers.",
            topic="NVIDIA Blackwell shipment delay",
        )
    ]
    u = heuristic_understand(
        text="Blackwell shipment delay reported by NVIDIA for Q4 deliveries",
        provider="news",
    )
    assert u.is_issue_candidate
    # Boost event text similarity for heuristic
    u.event = "NVIDIA delays Blackwell shipment to customers"
    u.topic = "NVIDIA Blackwell shipment delay"
    m = heuristic_match(u, existing)
    assert m.decision == DECISION_UPDATE
    assert m.existing_issue_id == "iss-1"


def test_golden_b_same_entity_different_event_new():
    """Case B: demand vs new chip announce → NEW."""
    existing = [
        ExistingIssueBrief(
            id="iss-1",
            title="NVIDIA Blackwell demand remains strong",
            summary="Hyperscalers keep ordering Blackwell GPUs.",
            topic="Blackwell demand",
        )
    ]
    u = heuristic_understand(
        text="NVIDIA announces brand new AI chip architecture separate from Blackwell demand",
        provider="news",
    )
    u.is_issue_candidate = True
    u.novelty = "new_development"
    u.topic = "new AI chip announce"
    u.event = "NVIDIA announces new AI chip architecture"
    u.entities = ["NVIDIA"]
    m = heuristic_match(u, existing)
    assert m.decision == DECISION_NEW


def test_golden_c_opinion_reject():
    u = heuristic_understand(
        text="I think NVIDIA will dominate AI forever and nothing else matters",
        provider="x",
    )
    m = heuristic_match(u, [])
    assert u.is_issue_candidate is False or m.decision == DECISION_REJECT


def test_golden_d_low_engagement_still_candidate():
    """Low replies must not block candidate acceptance."""
    d = priority_score(
        provider="official",
        published_at=None,
        payload={"public_metrics": {"reply_count": 0, "like_count": 1}},
    )
    assert d.accepted_into_pool is True
    u = heuristic_understand(
        text="NVIDIA officially announces Blackwell Ultra product launch for data centers",
        provider="official",
    )
    assert u.is_issue_candidate is True


def test_golden_e_cross_source_same_event():
    existing = [
        ExistingIssueBrief(
            id="iss-x",
            title="Fed holds rates steady",
            summary="The Federal Reserve left interest rates unchanged.",
            topic="Fed rates hold",
        )
    ]
    u = heuristic_understand(
        text="Reuters: Federal Reserve keeps interest rates unchanged at meeting",
        provider="news",
    )
    u.event = "Federal Reserve left interest rates unchanged"
    u.topic = "Fed rates hold"
    u.is_issue_candidate = True
    m = heuristic_match(u, existing)
    assert m.decision == DECISION_UPDATE


def test_trust_tier_mapping():
    assert trust_tier_for_provider("official") == "OFFICIAL"
    assert trust_tier_for_provider("news") == "NEWS"
    assert trust_tier_for_provider("x") == "SOCIAL"


def test_issue_quality_read_only_when_bad_options():
    sig = MarketSignal(
        title="테스트 이슈 제목입니다",
        summary="충분히 긴 요약문입니다. 두 문장 이상 필요합니다.",
        why_it_matters="중요합니다",
        participation_suitable=True,
        participation_options=["하나만"],
        providers=["news"],
        source_urls=["https://example.com"],
    )
    d = passes_issue_quality_gate(sig, source_count=1)
    assert d.accepted is True
    assert d.signal.participation_suitable is False
    assert d.signal.status.value == "draft"
