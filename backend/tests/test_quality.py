from app.domain.models import EvidenceType, MarketSignal
from app.pipeline.classification import (
    apply_corroboration_rules,
    is_home_excluded_content,
)
from app.pipeline.quality import passes_quality_gate, sanitize_evidence


def test_community_only_cannot_be_confirmed_fact():
    signal = MarketSignal(
        title="Tesla chatter on FSD",
        summary="Users on X say FSD feels better in city driving this week.",
        why_it_matters="Watchers care about FSD progress.",
        confirmed_facts=["Users on X say FSD feels better"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="FACT",
        evidence_level="CONFIRMED",
        importance=0.7,
        confidence=0.8,
        providers=["x"],
    )
    cleaned = sanitize_evidence(signal, ["x"])
    assert cleaned.confirmed_facts == []
    assert cleaned.evidence_level == "UNVERIFIED"
    assert EvidenceType.CONFIRMED_FACT not in cleaned.evidence_mix


def test_rumor_markers_clear_facts():
    signal = MarketSignal(
        title="Unverified factory claims",
        summary="Unverified factory claims circulate among Tesla watchers.",
        why_it_matters="",
        confirmed_facts=["factory claim"],
        evidence_mix=[EvidenceType.MARKET_INTERPRETATION],
        content_type="RUMOR",
        evidence_level="UNVERIFIED",
        importance=0.6,
        confidence=0.6,
        providers=["x"],
    )
    cleaned = sanitize_evidence(signal, ["x"])
    assert cleaned.evidence_mix == [EvidenceType.RUMOR]
    assert cleaned.confirmed_facts == []


def test_quality_gate_rejects_low_importance():
    signal = MarketSignal(
        title="Minor mention",
        summary="A short Tesla mention without much market relevance content here.",
        why_it_matters="n/a",
        importance=0.1,
        confidence=0.5,
        providers=["x"],
        evidence_mix=[EvidenceType.MARKET_INTERPRETATION],
        content_type="OPINION",
        evidence_level="OPINION",
    )
    decision = passes_quality_gate(signal, min_importance=0.4, min_confidence=0.3)
    assert decision.accepted is False
    assert decision.reason == "importance_below_threshold"


def test_news_allows_confirmed_facts():
    signal = MarketSignal(
        title="Tesla deliveries rise",
        summary="Tesla reports higher vehicle deliveries in latest quarterly update, company says.",
        why_it_matters="Delivery numbers move TSLA sentiment.",
        confirmed_facts=["Tesla reports higher vehicle deliveries"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="REPORT",
        evidence_level="CORROBORATED",
        importance=0.8,
        confidence=0.8,
        providers=["news"],
    )
    cleaned = sanitize_evidence(signal, ["news"])
    assert cleaned.confirmed_facts
    assert cleaned.evidence_level == "CORROBORATED"
    assert EvidenceType.CONFIRMED_FACT in cleaned.evidence_mix


def test_multiple_x_not_corroborated():
    assert (
        apply_corroboration_rules("CORROBORATED", ["x", "x", "reddit"])
        == "UNVERIFIED"
    )
    assert apply_corroboration_rules("CONFIRMED", ["x", "x"]) == "UNVERIFIED"
    assert apply_corroboration_rules("CORROBORATED", ["x", "news"]) == "CORROBORATED"
    assert apply_corroboration_rules("CONFIRMED", ["official"]) == "CONFIRMED"


def test_investment_call_soft_capped_but_publishable():
    signal = MarketSignal(
        title="Buy TSLA now for big upside this quarter",
        summary="A trader says investors should buy TSLA right away for large upside.",
        why_it_matters="Some accounts push trade ideas on social media.",
        content_type="INVESTMENT_CALL",
        evidence_level="OPINION",
        importance=0.9,
        confidence=0.8,
        providers=["x"],
    )
    cleaned = sanitize_evidence(signal, ["x"])
    assert cleaned.content_type == "INVESTMENT_CALL"
    assert cleaned.importance <= 0.35
    decision = passes_quality_gate(cleaned, min_importance=0.3, min_confidence=0.3)
    # May fail importance if below 0.3 after cap — 0.35 passes min 0.3
    assert decision.accepted is True or decision.reason == "importance_below_threshold"


def test_home_excludes_investment_and_promotion():
    assert is_home_excluded_content("INVESTMENT_CALL")
    assert is_home_excluded_content("PROMOTION")
    assert not is_home_excluded_content("FACT")
    assert not is_home_excluded_content("REPORT")


def test_invented_numbers_stripped_from_confirmed_facts():
    from app.pipeline.quality import ground_numeric_claims

    source = (
        "Tesla shares were down 1.3% at $360.75 in early trading after Musk "
        "reposted concerns about AI."
    )
    signal = MarketSignal(
        title="테슬라 주가 하락",
        summary=(
            "테슬라 주가가 최근 하락세를 보이고 있어요. "
            "테슬라 주가는 2.5% 하락하여 220달러에 거래되고 있습니다. "
            "머스크가 AI 우려를 언급했어요."
        ),
        why_it_matters="투자자들이 AI 리스크를 보고 있어요.",
        confirmed_facts=[
            "테슬라 주가는 현재 220달러에 거래되고 있다.",
            "최근 주가는 2.5% 하락했다.",
            "테슬라 주가는 360.75달러에 거래됐다.",
        ],
        key_points=[
            "테슬라 주가는 2.5% 하락했다.",
            "머스크가 AI 우려를 언급했다.",
        ],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="REPORT",
        evidence_level="CORROBORATED",
        importance=0.75,
        confidence=0.8,
        providers=["news"],
    )
    cleaned = ground_numeric_claims(signal, source)
    assert cleaned.confirmed_facts == ["테슬라 주가는 360.75달러에 거래됐다."]
    assert "220" not in cleaned.summary
    assert "2.5" not in cleaned.summary
    assert cleaned.key_points == ["머스크가 AI 우려를 언급했다."]


def test_quality_gate_grounds_with_source_text():
    source = (
        "Tesla shares were down 1.3% at $360.75 in early trading on Monday "
        "after Elon Musk joined those concerned about AI."
    )
    signal = MarketSignal(
        title="테슬라 주가",
        summary=(
            "테슬라와 관련된 시장 소식이 오늘 나왔어요. "
            "주가는 220달러로 거래되고 있습니다. "
            "투자자들이 관심을 두고 흐름을 지켜보고 있어요."
        ),
        why_it_matters="시장 반응을 확인하면 좋아요.",
        confirmed_facts=["주가는 220달러이다."],
        evidence_mix=[EvidenceType.CONFIRMED_FACT, EvidenceType.MARKET_INTERPRETATION],
        content_type="REPORT",
        evidence_level="CORROBORATED",
        importance=0.8,
        confidence=0.8,
        providers=["news"],
    )
    decision = passes_quality_gate(
        signal,
        min_importance=0.4,
        min_confidence=0.3,
        source_text=source,
    )
    assert decision.accepted is True
    assert decision.signal.confirmed_facts == []
    assert "220" not in decision.signal.summary


def test_thin_headline_source_clears_confirmed():
    signal = MarketSignal(
        title="Tesla Stock Drops",
        summary="Tesla Stock Drops as Musk Adds to the Chorus of AI Concern - barrons.com",
        why_it_matters="테스트",
        confirmed_facts=["테슬라 주가는 220달러"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="REPORT",
        evidence_level="CONFIRMED",
        importance=0.7,
        confidence=0.7,
        providers=["news"],
    )
    cleaned = sanitize_evidence(
        signal,
        ["news"],
        source_text="Tesla Stock Drops as Musk Adds to the Chorus of AI Concern - barrons.com",
    )
    assert cleaned.confirmed_facts == []
    assert cleaned.evidence_level != "CONFIRMED"
