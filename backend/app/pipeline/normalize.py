from __future__ import annotations

import hashlib
import re

# Extra aliases beyond ticker/company name for common US symbols.
SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "TSLA": ("tesla", "tsla", "fsd", "cybertruck", "optimus", "gigafactory"),
    "AAPL": ("apple", "aapl"),
    "MSFT": ("microsoft", "msft"),
    "NVDA": ("nvidia", "nvda"),
    "AMZN": ("amazon", "amzn"),
    "GOOGL": ("alphabet", "google", "googl"),
    "GOOG": ("alphabet", "google", "goog"),
    "META": ("meta", "facebook"),
    "BRK.B": ("berkshire", "brk.b", "brk b"),
    "JPM": ("jpmorgan", "jp morgan", "jpm"),
    "XOM": ("exxon", "exxonmobil", "xom"),
    "JNJ": ("johnson & johnson", "johnson and johnson", "jnj"),
    "V": ("visa",),
    "UNH": ("unitedhealth", "united health"),
    "HD": ("home depot",),
    "PG": ("procter", "p&g"),
    "AVGO": ("broadcom", "avgo"),
    "COST": ("costco",),
    "MU": ("micron", "mu"),
    "SCHD": ("schd",),
    "VYM": ("vym",),
    "SPY": ("spy", "s&p 500", "s&p500"),
    "QQQ": ("qqq", "nasdaq-100", "nasdaq 100"),
    "DIA": ("dia", "dow jones"),
}

# Default macro / geopolitics / commodity keep terms (override via MACRO_THEME_KEYWORDS).
DEFAULT_MACRO_THEME_KEYWORDS: tuple[str, ...] = (
    "fed",
    "fomc",
    "powell",
    "cpi",
    "inflation",
    "interest rate",
    "interest rates",
    "treasury",
    "yields",
    "bond yield",
    "oil",
    "crude",
    "brent",
    "wti",
    "opec",
    "trump",
    "white house",
    "tariff",
    "tariffs",
    "geopolit",
    "ukraine",
    "israel",
    "jobs report",
    "nonfarm",
    "payrolls",
    "unemployment",
    "gdp",
    "recession",
    "dollar index",
    "dxy",
)


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    return text.strip()


def content_fingerprint(text: str) -> str:
    normalized = normalize_text(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def keywords_for_symbol(symbol: str, name: str | None = None) -> list[str]:
    raw = (symbol or "").strip()
    # Keep KRX codes as zero-padded digits; US tickers uppercased.
    sym = raw.zfill(6) if raw.isdigit() else raw.upper()
    keys: list[str] = []
    if sym:
        keys.append(sym.lower() if not sym.isdigit() else sym)
        if sym.isdigit():
            keys.append(sym.lstrip("0") or sym)
    if name:
        keys.append(name.lower())
        keys.append(name)  # Korean names: casefold not always enough
    keys.extend(SYMBOL_ALIASES.get(sym if not sym.isdigit() else "", ()))
    keys.extend(SYMBOL_ALIASES.get(raw.upper(), ()))
    # Preserve order, drop empties/dupes.
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        k = (k or "").strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def is_relevant_to_symbol(text: str, symbol: str, name: str | None = None) -> bool:
    blob = text or ""
    lowered = blob.lower()
    if not blob.strip():
        return False
    for key in keywords_for_symbol(symbol, name):
        if not key:
            continue
        # Prefer case-insensitive Latin match; keep original for Hangul keys.
        haystack = lowered if key.isascii() else blob
        needle = key.lower() if key.isascii() else key
        if len(needle) <= 2 and needle.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack):
                return True
        elif needle in haystack:
            return True
    return False


def is_relevant_to_symbols(
    text: str,
    symbols: list[str] | set[str],
    names_by_symbol: dict[str, str] | None = None,
) -> bool:
    names_by_symbol = names_by_symbol or {}
    for symbol in symbols:
        raw = (symbol or "").strip()
        sym = raw.zfill(6) if raw.isdigit() else raw.upper()
        if is_relevant_to_symbol(text, sym, names_by_symbol.get(sym) or names_by_symbol.get(raw)):
            return True
    return False


def parse_macro_theme_keywords(raw: str | None = None) -> tuple[str, ...]:
    """Parse comma-separated macro keep terms; empty → product defaults."""
    if raw is None:
        return DEFAULT_MACRO_THEME_KEYWORDS
    text = (raw or "").strip()
    if not text:
        return DEFAULT_MACRO_THEME_KEYWORDS
    parts: list[str] = []
    seen: set[str] = set()
    for chunk in text.split(","):
        key = chunk.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        parts.append(key)
    return tuple(parts) if parts else DEFAULT_MACRO_THEME_KEYWORDS


def is_macro_theme(
    text: str,
    keywords: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True when text hits configured macro / geopolitics / commodity themes."""
    blob = (text or "").strip()
    if not blob:
        return False
    lowered = blob.lower()
    keys = keywords if keywords is not None else DEFAULT_MACRO_THEME_KEYWORDS
    for key in keys:
        k = (key or "").strip().lower()
        if not k:
            continue
        if len(k) <= 2:
            if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", lowered):
                return True
        elif k in lowered:
            return True
    return False


def is_keep_for_intelligence(
    text: str,
    symbols: list[str] | set[str],
    names_by_symbol: dict[str, str] | None = None,
    *,
    macro_keywords: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """Keep if watchlist/monitor symbol hit OR macro theme (Fed/oil/Trump/…)."""
    if is_relevant_to_symbols(text, symbols, names_by_symbol):
        return True
    return is_macro_theme(text, macro_keywords)
