"""Signal content_type / evidence_level helpers (shared classify + exposure)."""

from __future__ import annotations

from app.domain.models import ContentType, EvidenceLevel, EvidenceType

TRUSTED_PROVIDERS = frozenset({"news", "official", "sec", "ir"})
OFFICIAL_PROVIDERS = frozenset({"official", "sec", "ir"})
HOME_EXCLUDED_CONTENT_TYPES = frozenset(
    {ContentType.INVESTMENT_CALL.value, ContentType.PROMOTION.value}
)
CONFIRMED_USER_LEVELS = frozenset(
    {EvidenceLevel.CONFIRMED.value, EvidenceLevel.CORROBORATED.value}
)


def normalize_content_type(raw: str | None, *, default: str = ContentType.REPORT.value) -> str:
    key = (raw or "").strip().upper()
    for item in ContentType:
        if item.value == key:
            return item.value
    return default


def normalize_evidence_level(
    raw: str | None, *, default: str = EvidenceLevel.UNVERIFIED.value
) -> str:
    key = (raw or "").strip().upper()
    for item in EvidenceLevel:
        if item.value == key:
            return item.value
    return default


def has_trusted_provider(providers: list[str] | None) -> bool:
    return any((p or "").lower() in TRUSTED_PROVIDERS for p in (providers or []))


def has_official_provider(providers: list[str] | None) -> bool:
    return any((p or "").lower() in OFFICIAL_PROVIDERS for p in (providers or []))


def has_news_provider(providers: list[str] | None) -> bool:
    return any((p or "").lower() == "news" for p in (providers or []))


def only_community_providers(providers: list[str] | None) -> bool:
    """True when every provider is community (x/reddit) or empty."""
    cleaned = [(p or "").lower() for p in (providers or []) if p]
    if not cleaned:
        return True
    return all(p in {"x", "reddit"} for p in cleaned)


def apply_corroboration_rules(
    evidence_level: str,
    providers: list[str] | None,
) -> str:
    """
    Independent news/official required for CORROBORATED/CONFIRMED.
    Multiple X accounts alone never upgrade.
    """
    level = normalize_evidence_level(evidence_level)
    official = has_official_provider(providers)
    news = has_news_provider(providers)
    community_only = only_community_providers(providers)

    if level == EvidenceLevel.CONFIRMED.value:
        if official:
            return EvidenceLevel.CONFIRMED.value
        if news:
            return EvidenceLevel.CORROBORATED.value
        return EvidenceLevel.UNVERIFIED.value

    if level == EvidenceLevel.CORROBORATED.value:
        if official:
            return EvidenceLevel.CONFIRMED.value
        if news and not community_only:
            return EvidenceLevel.CORROBORATED.value
        if news:
            return EvidenceLevel.CORROBORATED.value
        return EvidenceLevel.UNVERIFIED.value

    if community_only and level not in {
        EvidenceLevel.OPINION.value,
        EvidenceLevel.UNVERIFIED.value,
    }:
        return EvidenceLevel.UNVERIFIED.value

    return level


def evidence_mix_for_level(level: str) -> list[EvidenceType]:
    """Keep legacy evidence_mix roughly aligned for older UI paths."""
    level = normalize_evidence_level(level)
    if level == EvidenceLevel.CONFIRMED.value:
        return [EvidenceType.CONFIRMED_FACT]
    if level == EvidenceLevel.CORROBORATED.value:
        return [EvidenceType.CONFIRMED_FACT, EvidenceType.MARKET_INTERPRETATION]
    if level == EvidenceLevel.OPINION.value:
        return [EvidenceType.OPINION]
    return [EvidenceType.RUMOR]


def is_home_excluded_content(content_type: str | None) -> bool:
    return normalize_content_type(content_type, default="") in HOME_EXCLUDED_CONTENT_TYPES


def is_confirmed_user_label(evidence_level: str | None) -> bool:
    return normalize_evidence_level(evidence_level) in CONFIRMED_USER_LEVELS


def heuristic_content_and_level(
    providers: list[str] | None,
    *,
    rumorish: bool,
) -> tuple[str, str]:
    """Provider-only fallback when LLM is off — no keyword buy/sell lists."""
    if rumorish:
        return ContentType.RUMOR.value, EvidenceLevel.UNVERIFIED.value
    if has_official_provider(providers):
        return ContentType.FACT.value, EvidenceLevel.CONFIRMED.value
    if has_news_provider(providers):
        return ContentType.REPORT.value, EvidenceLevel.CORROBORATED.value
    return ContentType.MARKET_REACTION.value, EvidenceLevel.UNVERIFIED.value
