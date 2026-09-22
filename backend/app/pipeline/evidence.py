"""Evidence helpers — trust tier hints for Issue cards (not truth gates)."""

from __future__ import annotations

TRUST_OFFICIAL = "OFFICIAL"
TRUST_NEWS = "NEWS"
TRUST_SOCIAL = "SOCIAL"
TRUST_COMMUNITY = "COMMUNITY"
TRUST_UNKNOWN = "UNKNOWN"


def trust_tier_for_provider(provider: str | None) -> str:
    p = (provider or "").strip().lower()
    if p in ("official", "sec", "ir", "dart"):
        return TRUST_OFFICIAL
    if p == "news":
        return TRUST_NEWS
    if p == "x":
        return TRUST_SOCIAL
    if p == "reddit":
        return TRUST_COMMUNITY
    return TRUST_UNKNOWN
