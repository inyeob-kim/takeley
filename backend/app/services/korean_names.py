"""Curated Korean display names for common US tickers (서학개미 UI)."""

from __future__ import annotations

# Familiar Korean names — not official legal names.
US_TICKER_NAME_KO: dict[str, str] = {
    "AAPL": "애플",
    "MSFT": "마이크로소프트",
    "NVDA": "엔비디아",
    "AMZN": "아마존",
    "GOOGL": "알파벳",
    "GOOG": "알파벳",
    "META": "메타",
    "TSLA": "테슬라",
    "BRK.B": "버크셔해서웨이",
    "BRK.A": "버크셔해서웨이",
    "JPM": "JP모건",
    "XOM": "엑슨모빌",
    "JNJ": "존슨앤존슨",
    "V": "비자",
    "MA": "마스터카드",
    "UNH": "유나이티드헬스",
    "HD": "홈디포",
    "PG": "P&G",
    "AVGO": "브로드컴",
    "COST": "코스트코",
    "NFLX": "넷플릭스",
    "AMD": "AMD",
    "MU": "마이크론",
    "INTC": "인텔",
    "CRM": "세일즈포스",
    "ORCL": "오라클",
    "ADBE": "어도비",
    "CSCO": "시스코",
    "PEP": "펩시코",
    "KO": "코카콜라",
    "DIS": "디즈니",
    "BA": "보잉",
    "CAT": "캐터필러",
    "GS": "골드만삭스",
    "WMT": "월마트",
    "SCHD": "SCHD",
    "VYM": "VYM",
    "SPY": "S&P500 ETF",
    "QQQ": "나스닥100 ETF",
    "DIA": "다우 ETF",
    "IWM": "러셀2000 ETF",
    "SNDK": "샌디스크",
    "WDC": "웨스턴디지털",
}

# English display names for monitor-set seed rows.
US_TICKER_NAME_EN: dict[str, str] = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "GOOG": "Alphabet",
    "META": "Meta",
    "TSLA": "Tesla",
    "BRK.B": "Berkshire Hathaway",
    "BRK.A": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase",
    "XOM": "Exxon Mobil",
    "JNJ": "Johnson & Johnson",
    "V": "Visa",
    "MA": "Mastercard",
    "UNH": "UnitedHealth",
    "HD": "Home Depot",
    "PG": "Procter & Gamble",
    "AVGO": "Broadcom",
    "COST": "Costco",
    "NFLX": "Netflix",
    "AMD": "AMD",
    "MU": "Micron",
    "INTC": "Intel",
    "CRM": "Salesforce",
    "ORCL": "Oracle",
    "ADBE": "Adobe",
    "CSCO": "Cisco",
    "PEP": "PepsiCo",
    "KO": "Coca-Cola",
    "DIS": "Disney",
    "BA": "Boeing",
    "CAT": "Caterpillar",
    "GS": "Goldman Sachs",
    "WMT": "Walmart",
    "SCHD": "Schwab US Dividend Equity ETF",
    "VYM": "Vanguard High Dividend Yield ETF",
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "IWM": "iShares Russell 2000 ETF",
    "SNDK": "SanDisk",
    "WDC": "Western Digital",
}


def name_ko_for(symbol: str, *, fallback: str | None = None) -> str | None:
    sym = (symbol or "").strip().upper()
    if not sym:
        return None
    if sym in US_TICKER_NAME_KO:
        return US_TICKER_NAME_KO[sym]
    return fallback


def name_en_for(symbol: str, *, fallback: str | None = None) -> str:
    sym = (symbol or "").strip().upper()
    if sym in US_TICKER_NAME_EN:
        return US_TICKER_NAME_EN[sym]
    return fallback or sym


def display_label(symbol: str, *, name_ko: str | None = None, name: str | None = None) -> str:
    """UI preference: Korean name → English name → ticker."""
    sym = (symbol or "").strip().upper()
    ko = (name_ko or "").strip() or name_ko_for(sym)
    if ko:
        return ko
    en = (name or "").strip()
    if en and en.upper() != sym:
        return en
    return sym
