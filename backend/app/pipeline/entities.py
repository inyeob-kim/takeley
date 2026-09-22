from __future__ import annotations

import re

from app.core.config import get_settings
from app.pipeline.normalize import SYMBOL_ALIASES, is_macro_theme
from app.services.korean_names import name_en_for

# Seed patterns for frequent tickers; universe extras matched via aliases/names.
SYMBOL_PATTERNS: dict[str, re.Pattern[str]] = {
    sym: re.compile(
        rf"\b({'|'.join(re.escape(a) for a in aliases if a.isascii())})\b",
        re.I,
    )
    for sym, aliases in SYMBOL_ALIASES.items()
    if any(a.isascii() and len(a) >= 2 for a in aliases)
}

SECTOR_KEYWORDS = {
    "EV": ("ev", "electric vehicle", "cybertruck"),
    "AI": ("ai", "autonomous", "llm", "data center"),
    "Semiconductor": ("chip", "semiconductor", "gpu", "memory", "dram", "hbm"),
    "Rates": (
        "fed",
        "fomc",
        "interest rate",
        "treasury",
        "yield",
        "cpi",
        "inflation",
        "powell",
    ),
    "Oil": ("oil", "crude", "brent", "wti", "opec"),
    "Geopolitics": ("trump", "tariff", "geopolit", "ukraine", "israel", "white house"),
}


def default_universe_symbols() -> list[str]:
    """Monitor set ∪ MVP — used when analyze has no explicit universe."""
    settings = get_settings()
    out: list[str] = []
    seen: set[str] = set()
    for sym in (*settings.monitor_symbols(), settings.mvp_asset_symbol.upper()):
        s = (sym or "").strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def extract_symbols(text: str, extra_symbols: list[str] | None = None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def _add(sym: str) -> None:
        s = sym.upper()
        if s and s not in seen:
            seen.add(s)
            found.append(s)

    for symbol, pattern in SYMBOL_PATTERNS.items():
        if pattern.search(text):
            _add(symbol)

    # Universe tickers: match ticker token, aliases, or English display name.
    candidates = list(extra_symbols) if extra_symbols is not None else default_universe_symbols()
    lowered = text.lower()
    for symbol in candidates:
        sym = (symbol or "").strip().upper()
        if not sym or sym in seen:
            continue
        hit = False
        if re.search(rf"\b{re.escape(sym)}\b", text, re.I):
            hit = True
        else:
            aliases = list(SYMBOL_ALIASES.get(sym, ()))
            en = name_en_for(sym)
            if en:
                aliases.append(en.lower())
            for alias in aliases:
                a = (alias or "").strip().lower()
                if not a:
                    continue
                if len(a) <= 2:
                    if re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", lowered):
                        hit = True
                        break
                elif a in lowered:
                    hit = True
                    break
        if hit:
            _add(sym)
    return found


def extract_sectors(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            found.append(sector)
    if not found and is_macro_theme(text):
        found.append("Macro")
    return found
