"""Prompt calibration anchors + quality cases A–E (no LLM calls)."""

from app.domain.models import EvidenceType, MarketSignal
from app.pipeline.prompts import (
    BRIEF_SYNTHESIZE_PROMPT,
    PERSONAL_SIGNAL_SELECT_PROMPT,
    SIGNAL_ANALYSIS_PROMPT,
)
from app.pipeline.quality import passes_quality_gate, sanitize_evidence


def test_signal_prompt_defines_is_relevant_vs_importance():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "is_relevant" in text
    assert "content_type" in text
    assert "evidence_level" in text
    assert "INVESTMENT_CALL" in text
    assert "participation_suitable" in text
    assert "KOREAN" in text or "Korean" in text


def test_signal_prompt_asks_for_detail_length():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "key_points" in text
    assert "participation_options" in text
    assert "NEVER invent controversy" in text or "participation_suitable" in text


def test_signal_prompt_version_is_issue_card_v4():
    from app.pipeline.prompts import SIGNAL_ANALYSIS_PROMPT_VERSION

    assert SIGNAL_ANALYSIS_PROMPT_VERSION == "issue_card_v4"


def test_signal_prompt_trending_is_ai_not_keyword():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "is_trending" in text
    assert "NOT keyword" in text or "keyword matching" in text


def test_signal_prompt_requires_fact_preservation():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "Do NOT invent facts" in text or "Do NOT invent" in text
    assert "confirmed_facts" in text


def test_signal_prompt_requires_llm_emphasis():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "emphasis" in text
    assert "key_sentences" in text
    assert "rise_numbers" in text
    assert "fall_numbers" in text


def test_signal_prompt_has_importance_and_confidence_bands():
    text = SIGNAL_ANALYSIS_PROMPT
    assert "importance" in text
    assert "confidence" in text
    assert "INVESTMENT_CALL" in text
    assert "CORROBORATED" in text
    assert "participation_type" in text


def test_personal_select_prompt_priority_order():
    text = PERSONAL_SIGNAL_SELECT_PROMPT
    assert "CONFIRMED or CORROBORATED" in text
    assert "INVESTMENT_CALL" in text
    assert "{slot_count}" in text
    assert '"selected"' in text


def test_brief_prompt_keeps_no_invent_and_no_advice():
    text = BRIEF_SYNTHESIZE_PROMPT
    assert "Never invent facts beyond the provided signals." in text
    assert "not confirmed yet" in text or "아직 확인" in text
    assert "Never present investment calls" in text
    assert "~해요" in text


def test_case_a_official_major_event_stays_confirmed():
    signal = MarketSignal(
        title="Tesla deliveries rise",
        summary="Tesla reports higher vehicle deliveries in the latest quarter.",
        why_it_matters="Delivery numbers can move TSLA sentiment.",
        confirmed_facts=["Tesla reports higher vehicle deliveries"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="FACT",
        evidence_level="CONFIRMED",
        importance=0.92,
        confidence=0.93,
        providers=["news", "official"],
    )
    cleaned = sanitize_evidence(signal, ["news", "official"])
    decision = passes_quality_gate(cleaned, min_importance=0.4, min_confidence=0.3)
    assert decision.accepted is True
    assert cleaned.importance >= 0.9
    assert cleaned.evidence_level == "CONFIRMED"
    assert cleaned.confirmed_facts


def test_case_b_important_rumor_not_confirmed():
    signal = MarketSignal(
        title="Unverified factory expansion rumor",
        summary="Unverified reports say Tesla may open a huge new factory next year.",
        why_it_matters="If true, capacity expectations could shift.",
        confirmed_facts=["Tesla will open a huge new factory"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="RUMOR",
        evidence_level="CONFIRMED",
        importance=0.85,
        confidence=0.25,
        providers=["x"],
    )
    cleaned = sanitize_evidence(signal, ["x"])
    assert cleaned.confirmed_facts == []
    assert cleaned.evidence_level == "UNVERIFIED"
    assert EvidenceType.RUMOR in cleaned.evidence_mix
    assert cleaned.confidence <= 0.35
    assert cleaned.importance >= 0.7


def test_case_c_official_but_small_impact_can_pass_with_mid_importance():
    signal = MarketSignal(
        title="Minor IR schedule note",
        summary="Company posts a routine IR calendar update with no new guidance.",
        why_it_matters="Useful for tracking, but not a big market mover.",
        confirmed_facts=["Company posts a routine IR calendar update"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="FACT",
        evidence_level="CONFIRMED",
        importance=0.45,
        confidence=0.9,
        providers=["ir", "official"],
    )
    cleaned = sanitize_evidence(signal, ["ir", "official"])
    decision = passes_quality_gate(cleaned, min_importance=0.4, min_confidence=0.3)
    assert decision.accepted is True
    assert cleaned.confidence >= 0.7
    assert 0.4 <= cleaned.importance < 0.7


def test_case_d_weak_chatter_rejected_by_gate():
    signal = MarketSignal(
        title="Vague Tesla chatter",
        summary="People keep saying Tesla feels exciting lately without new facts.",
        why_it_matters="",
        evidence_mix=[EvidenceType.OPINION],
        importance=0.2,
        confidence=0.2,
        providers=["x"],
    )
    decision = passes_quality_gate(signal, min_importance=0.4, min_confidence=0.3)
    assert decision.accepted is False
    assert signal.importance < 0.3
    assert signal.confidence < 0.3


def test_case_e_community_only_clears_confirmed_facts():
    signal = MarketSignal(
        title="Reddit says buyout coming",
        summary="Reddit threads claim a buyout is coming soon.",
        why_it_matters="Would matter if true, but source is community only.",
        confirmed_facts=["Buyout is coming soon"],
        evidence_mix=[EvidenceType.CONFIRMED_FACT],
        content_type="RUMOR",
        evidence_level="CONFIRMED",
        importance=0.75,
        confidence=0.7,
        providers=["reddit"],
    )
    cleaned = sanitize_evidence(signal, ["reddit"])
    assert cleaned.confirmed_facts == []
    assert cleaned.evidence_level == "UNVERIFIED"
    assert EvidenceType.CONFIRMED_FACT not in cleaned.evidence_mix
