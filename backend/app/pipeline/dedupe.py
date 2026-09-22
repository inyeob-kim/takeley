from __future__ import annotations

from difflib import SequenceMatcher


def is_near_duplicate(a: str, b: str, threshold: float = 0.9) -> bool:
    if not a or not b:
        return False
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return ratio >= threshold
