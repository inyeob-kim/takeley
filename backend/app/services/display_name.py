"""Anonymous device-user display names (nickname)."""

from __future__ import annotations

DISPLAY_NAME_MIN_LEN = 2
DISPLAY_NAME_MAX_LEN = 16


def normalize_display_name(value: str | None) -> str | None:
    """
    Normalize a nickname for storage.

    - None / blank → None (anonymous)
    - Non-empty must be 2–16 chars after strip; no control whitespace
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if any(ch in raw for ch in ("\n", "\r", "\t")):
        raise ValueError("display_name must be a single line")
    if len(raw) < DISPLAY_NAME_MIN_LEN or len(raw) > DISPLAY_NAME_MAX_LEN:
        raise ValueError(
            f"display_name must be {DISPLAY_NAME_MIN_LEN}–{DISPLAY_NAME_MAX_LEN} characters"
        )
    return raw
