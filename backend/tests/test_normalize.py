from app.pipeline.normalize import is_relevant_to_symbol, is_relevant_to_symbols


def test_micron_relevance():
    assert is_relevant_to_symbol("Micron raises DRAM guidance", "MU", "Micron")
    assert is_relevant_to_symbol("MU shares jump on memory demand", "MU", "Micron")
    assert not is_relevant_to_symbol("Apple unveils new phone", "MU", "Micron")


def test_universe_relevance():
    assert is_relevant_to_symbols(
        "Nvidia data center growth",
        ["TSLA", "NVDA"],
        {"NVDA": "Nvidia", "TSLA": "Tesla"},
    )
    assert is_relevant_to_symbols(
        "Tesla FSD update",
        ["TSLA", "MU"],
        {"TSLA": "Tesla", "MU": "Micron"},
    )


def test_apple_and_exxon_aliases():
    assert is_relevant_to_symbol("Apple launches new iPhone", "AAPL", "Apple")
    assert is_relevant_to_symbols(
        "Exxon production update",
        ["XOM"],
        {"XOM": "Exxon Mobil"},
    )
