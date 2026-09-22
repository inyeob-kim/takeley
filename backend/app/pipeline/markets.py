"""Market region helpers for ingest routing (US vs KR equities)."""

from __future__ import annotations

import re

from app.services.universe import UniverseSymbol

_KR_STOCK_RE = re.compile(r"^\d{6}$")


def is_kr_equity_symbol(symbol: str | None) -> bool:
    """KRX-style 6-digit codes (e.g. 005930)."""
    return bool(_KR_STOCK_RE.match((symbol or "").strip()))


def is_us_equity_symbol(symbol: str | None) -> bool:
    """Non-KR ticker symbols used for X / Finnhub / EN Google RSS."""
    sym = (symbol or "").strip().upper()
    if not sym or is_kr_equity_symbol(sym):
        return False
    return True


def split_universe(
    universe: list[UniverseSymbol],
) -> tuple[list[UniverseSymbol], list[UniverseSymbol]]:
    """Return (us_symbols, kr_symbols)."""
    us: list[UniverseSymbol] = []
    kr: list[UniverseSymbol] = []
    for entry in universe:
        if is_kr_equity_symbol(entry.symbol):
            kr.append(entry)
        else:
            us.append(entry)
    return us, kr


def search_query_for_kr(entry: UniverseSymbol) -> str:
    """Korean Google News query: prefer company name + stock code."""
    name = (entry.name or "").strip()
    sym = entry.symbol.strip()
    if name and name != sym:
        return f"{name} OR {sym}"
    return sym
