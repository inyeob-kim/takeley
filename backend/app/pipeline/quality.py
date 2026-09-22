"""Quality gates for publishing Market Signals (Tesla PoC)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.domain.models import (
    ContentType,
    EvidenceLevel,
    EvidenceType,
    MarketSignal,
    SignalStatus,
)
from app.pipeline.classification import (
    apply_corroboration_rules,
    evidence_mix_for_level,
    has_trusted_provider,
    is_home_excluded_content,
    normalize_content_type,
    normalize_evidence_level,
    only_community_providers,
)

logger = logging.getLogger(__name__)

# Re-export for older imports
TRUSTED_PROVIDERS = frozenset({"news", "official", "sec", "ir"})


def has_trusted_source(providers: list[str]) -> bool:
    return has_trusted_provider(providers)

RUMOR_MARKERS = (
    "rumor",
    "allegedly",
    "unverified",
    "sources say",
    "could be",
    "might be",
    "unconfirmed",
    "circulating",
)

# Prices, percents, plain figures — used to block invented numbers.
_NUM_RE = re.compile(
    r"(?<![\w./])(?:\$)?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?"
    r"|(?<![\w./])(?:\$)?\d+(?:\.\d+)?%?"
    r"|(?<![\w./])\d+(?:\.\d+)?%",
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+|\n+")


def _normalize_number_token(token: str) -> str:
    t = (token or "").strip().replace(",", "").replace("$", "").replace("%", "")
    if not t:
        return ""
    try:
        val = float(t)
        if val.is_integer():
            return str(int(val))
        return f"{val:.6f}".rstrip("0").rstrip(".")
    except ValueError:
        return t


def extract_number_tokens(text: str) -> list[str]:
    return [_normalize_number_token(m.group(0)) for m in _NUM_RE.finditer(text or "")]


def _numbers_grounded(text: str, source_nums: set[str]) -> bool:
    nums = [n for n in extract_number_tokens(text) if n]
    if not nums:
        return True
    return all(n in source_nums for n in nums)


def _filter_list_by_source(items: list[str], source_nums: set[str]) -> tuple[list[str], int]:
    kept: list[str] = []
    dropped = 0
    for item in items or []:
        text = (item or "").strip()
        if not text:
            continue
        if _numbers_grounded(text, source_nums):
            kept.append(text)
        else:
            dropped += 1
    return kept, dropped


def _filter_prose_by_source(text: str, source_nums: set[str]) -> tuple[str, int]:
    """Drop sentences that contain numbers absent from source."""
    raw = (text or "").strip()
    if not raw:
        return "", 0
    if _numbers_grounded(raw, source_nums):
        return raw, 0

    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(raw) if p and p.strip()]
    if len(parts) <= 1:
        # Single blob with invented numbers — cannot safely keep it.
        return "", 1

    kept: list[str] = []
    dropped = 0
    for part in parts:
        if _numbers_grounded(part, source_nums):
            kept.append(part)
        else:
            dropped += 1
    return " ".join(kept).strip(), dropped


def _filter_emphasis(emphasis: dict, source_nums: set[str], body: str) -> dict:
    data = emphasis if isinstance(emphasis, dict) else {}
    body_norm = body or ""

    def _keep_number_tokens(values) -> list[str]:
        out: list[str] = []
        for item in values or []:
            token = str(item or "").strip()
            if not token or token in out:
                continue
            nums = [n for n in extract_number_tokens(token) if n]
            if not nums:
                # Non-numeric emphasis tokens must appear in body text.
                if token in body_norm:
                    out.append(token)
                continue
            if not all(n in source_nums for n in nums):
                continue
            # Prefer tokens that literally appear; else keep normalized digits found in source.
            if token in body_norm or all(n in source_nums for n in nums):
                out.append(token)
        return out[:12]

    key_sentences: list[str] = []
    for item in data.get("key_sentences") or []:
        sentence = str(item or "").strip()
        if not sentence or sentence not in body_norm:
            continue
        if not _numbers_grounded(sentence, source_nums):
            continue
        if sentence not in key_sentences:
            key_sentences.append(sentence)
        if len(key_sentences) >= 3:
            break

    rise = _keep_number_tokens(data.get("rise_numbers"))
    fall = [t for t in _keep_number_tokens(data.get("fall_numbers")) if t not in rise]
    return {
        "key_sentences": key_sentences,
        "rise_numbers": rise,
        "fall_numbers": fall,
    }


def ground_signal_to_source(signal: MarketSignal, source_text: str) -> MarketSignal:
    """
    Remove invented numeric claims from facts, bullets, and prose fields
    when those numbers are absent from the source cluster text.
    """
    source_nums = {n for n in extract_number_tokens(source_text) if n}
    facts, dropped_facts = _filter_list_by_source(
        list(signal.confirmed_facts or []), source_nums
    )
    points, dropped_points = _filter_list_by_source(
        list(signal.key_points or []), source_nums
    )
    summary, dropped_summary = _filter_prose_by_source(signal.summary or "", source_nums)
    why, dropped_why = _filter_prose_by_source(signal.why_it_matters or "", source_nums)
    # If invented numbers wiped the summary, fall back to a grounded source excerpt.
    if not summary and (source_text or "").strip():
        excerpt = " ".join((source_text or "").split())
        summary = excerpt[:500].rstrip()
        if len(excerpt) > 500:
            summary += "…"
        dropped_summary = max(dropped_summary, 1)

    reaction = signal.market_reaction
    dropped_reaction = 0
    if reaction:
        reaction, dropped_reaction = _filter_prose_by_source(reaction, source_nums)
        if not reaction:
            reaction = None

    body_for_emphasis = f"{summary}\n{why}"
    emphasis = _filter_emphasis(signal.emphasis or {}, source_nums, body_for_emphasis)

    dropped_total = (
        dropped_facts + dropped_points + dropped_summary + dropped_why + dropped_reaction
    )
    if dropped_total:
        logger.info(
            "ground_signal dropped_parts=%s facts=%s points=%s prose=%s title=%s",
            dropped_total,
            dropped_facts,
            dropped_points,
            dropped_summary + dropped_why + dropped_reaction,
            (signal.title or "")[:80],
        )

    signal.confirmed_facts = facts
    signal.key_points = points
    signal.summary = summary
    signal.why_it_matters = why
    signal.market_reaction = reaction
    signal.emphasis = emphasis

    if not facts and EvidenceType.CONFIRMED_FACT in (signal.evidence_mix or []):
        signal.evidence_mix = [
            e for e in signal.evidence_mix if e != EvidenceType.CONFIRMED_FACT
        ]
        if not signal.evidence_mix:
            signal.evidence_mix = [EvidenceType.MARKET_INTERPRETATION]
        signal.confidence = min(signal.confidence, 0.55)
    return signal


# Back-compat alias used by older tests/imports.
def ground_numeric_claims(signal: MarketSignal, source_text: str) -> MarketSignal:
    return ground_signal_to_source(signal, source_text)


def source_body_is_thin(source_text: str, *, min_chars: int = 280) -> bool:
    return len((source_text or "").strip()) < min_chars


@dataclass
class QualityDecision:
    accepted: bool
    reason: str
    signal: MarketSignal


def has_trusted_source(providers: list[str]) -> bool:
    return any(p in TRUSTED_PROVIDERS for p in providers)


def looks_like_rumor(text: str) -> bool:
    lowered = text.lower()
    return any(m in lowered for m in RUMOR_MARKERS)


def sanitize_evidence(
    signal: MarketSignal,
    providers: list[str],
    *,
    source_text: str | None = None,
) -> MarketSignal:
    """Apply corroboration rules + grounding. No keyword buy/sell filters."""
    providers = providers or signal.providers or []

    signal.content_type = normalize_content_type(
        getattr(signal, "content_type", None),
        default=ContentType.REPORT.value,
    )
    signal.evidence_level = normalize_evidence_level(
        getattr(signal, "evidence_level", None),
        default=EvidenceLevel.UNVERIFIED.value,
    )
    signal.evidence_level = apply_corroboration_rules(
        signal.evidence_level, providers
    )

    # Soft-cap promotional / tipster signals (still publishable; Home/Brief filter later).
    if is_home_excluded_content(signal.content_type):
        signal.importance = min(float(signal.importance or 0), 0.35)
        signal.confidence = min(float(signal.confidence or 0), 0.4)
        if signal.evidence_level not in {
            EvidenceLevel.OPINION.value,
            EvidenceLevel.UNVERIFIED.value,
        }:
            signal.evidence_level = EvidenceLevel.OPINION.value

    community_only = only_community_providers(providers)
    if community_only:
        signal.confirmed_facts = []
        if signal.evidence_level in {
            EvidenceLevel.CONFIRMED.value,
            EvidenceLevel.CORROBORATED.value,
        }:
            signal.evidence_level = EvidenceLevel.UNVERIFIED.value

    # Align legacy evidence_mix for older clients.
    signal.evidence_mix = evidence_mix_for_level(signal.evidence_level)

    # Confidence ceilings by evidence level (not "X provider" alone).
    if signal.evidence_level == EvidenceLevel.UNVERIFIED.value:
        signal.confidence = min(float(signal.confidence or 0), 0.55)
    elif signal.evidence_level == EvidenceLevel.OPINION.value:
        signal.confidence = min(float(signal.confidence or 0), 0.45)
    elif signal.evidence_level == EvidenceLevel.CORROBORATED.value:
        signal.confidence = min(float(signal.confidence or 0), 0.85)

    cleaned_facts = [
        f.strip()
        for f in (signal.confirmed_facts or [])
        if f and f.strip() and not looks_like_rumor(f)
    ]
    if signal.evidence_level not in {
        EvidenceLevel.CONFIRMED.value,
        EvidenceLevel.CORROBORATED.value,
    }:
        cleaned_facts = []
    signal.confirmed_facts = cleaned_facts

    if source_text is not None and source_body_is_thin(source_text):
        signal.confirmed_facts = []
        if signal.evidence_level == EvidenceLevel.CONFIRMED.value:
            signal.evidence_level = (
                EvidenceLevel.CORROBORATED.value
                if has_trusted_provider(providers)
                else EvidenceLevel.UNVERIFIED.value
            )
        signal.evidence_mix = evidence_mix_for_level(signal.evidence_level)
        signal.confidence = min(float(signal.confidence or 0), 0.5)
        logger.info(
            "sanitize thin_source title=%s level=%s",
            (signal.title or "")[:80],
            signal.evidence_level,
        )
        signal = ground_signal_to_source(signal, source_text)
    elif source_text is not None:
        signal = ground_signal_to_source(signal, source_text)

    if not signal.evidence_mix:
        signal.evidence_mix = evidence_mix_for_level(signal.evidence_level)

    # Independent provider diversity still helps ranking slightly.
    distinct = { (p or "").lower() for p in providers if p }
    if len(distinct) >= 2 and not only_community_providers(providers):
        signal.importance = min(1.0, float(signal.importance or 0) + 0.1)
        signal.confidence = min(1.0, float(signal.confidence or 0) + 0.05)
    return signal


def passes_quality_gate(
    signal: MarketSignal,
    *,
    min_importance: float,
    min_confidence: float,
    source_text: str | None = None,
) -> QualityDecision:
    signal = sanitize_evidence(
        signal,
        signal.providers,
        source_text=source_text,
    )

    if len((signal.summary or "").strip()) < 40:
        signal.status = SignalStatus.REJECTED
        return QualityDecision(False, "summary_too_short", signal)

    if signal.importance < min_importance:
        signal.status = SignalStatus.REJECTED
        return QualityDecision(False, "importance_below_threshold", signal)

    if signal.confidence < min_confidence:
        signal.status = SignalStatus.REJECTED
        return QualityDecision(False, "confidence_below_threshold", signal)

    signal.status = SignalStatus.PUBLISHED
    return QualityDecision(True, "ok", signal)
