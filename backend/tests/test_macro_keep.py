"""Macro theme keep path + wider symbol extract."""

from app.pipeline.entities import extract_sectors, extract_symbols
from app.pipeline.normalize import (
    is_keep_for_intelligence,
    is_macro_theme,
    is_relevant_to_symbols,
)


def test_macro_theme_fed_oil_trump():
    assert is_macro_theme("Fed signals pause on rate cuts after CPI print")
    assert is_macro_theme("Oil jumps as OPEC talks supply cuts")
    assert is_macro_theme("Trump tariff comments rattle risk assets")
    assert not is_macro_theme("Local bakery opens a new cafe downtown")


def test_keep_for_intelligence_symbol_or_macro():
    names = {"AAPL": "Apple", "SPY": "SPDR S&P 500"}
    assert is_keep_for_intelligence(
        "Apple supplier update ahead of earnings",
        ["AAPL", "MSFT"],
        names,
    )
    assert is_keep_for_intelligence(
        "FOMC minutes show divided views on rates",
        ["AAPL"],
        names,
    )
    assert not is_keep_for_intelligence(
        "Celebrity gossip with no market angle",
        ["AAPL"],
        names,
    )


def test_extract_symbols_from_universe_names():
    found = extract_symbols(
        "Apple and Microsoft rally while Nvidia cools",
        extra_symbols=["AAPL", "MSFT", "NVDA", "XOM"],
    )
    assert "AAPL" in found
    assert "MSFT" in found
    assert "NVDA" in found


def test_extract_sectors_rates_oil():
    sectors = extract_sectors("Treasury yields rise after hotter CPI")
    assert "Rates" in sectors
    oil = extract_sectors("Brent crude climbs on OPEC chatter")
    assert "Oil" in oil


def test_universe_relevance_still_works():
    assert is_relevant_to_symbols(
        "Exxon Mobil production update",
        ["XOM", "AAPL"],
        {"XOM": "Exxon Mobil", "AAPL": "Apple"},
    )
