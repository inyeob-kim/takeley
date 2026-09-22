from app.pipeline.industries import (
    INDUSTRY_LABELS,
    ISSUE_INDUSTRY_KEYS,
    SOURCE_LANES,
    build_topic_lanes,
    category_filter_values,
    discovery_query_for,
    legacy_topic_since_cursor_key,
    normalize_industry_category,
    parse_industry_keys,
    select_topic_lanes,
    topic_since_cursor_key,
)


def test_parse_industry_keys_default():
    keys = parse_industry_keys("")
    assert keys == ISSUE_INDUSTRY_KEYS
    assert len(keys) == 10


def test_parse_industry_keys_subset():
    keys = parse_industry_keys("AI, politics, junk, society")
    assert keys == ("ai", "politics", "society")


def test_normalize_industry_category():
    assert normalize_industry_category("ai") == "AI"
    assert normalize_industry_category("Technology") == "기술"
    assert normalize_industry_category("Tech") == "기술"
    assert normalize_industry_category("Politics") == "정치"
    assert normalize_industry_category("정치") == "정치"
    assert normalize_industry_category("엔터") == "엔터"
    assert normalize_industry_category("entertainment") == "엔터"
    assert normalize_industry_category("random") is None
    assert normalize_industry_category("korea") is None
    assert normalize_industry_category("global") is None


def test_category_filter_includes_legacy():
    vals = category_filter_values("기술")
    assert vals is not None
    assert "기술" in vals
    assert "Tech" in vals


def test_industry_labels_cover_keys():
    for key in ISSUE_INDUSTRY_KEYS:
        assert key in INDUSTRY_LABELS
    assert INDUSTRY_LABELS["politics"] == "정치"
    assert INDUSTRY_LABELS["entertainment"] == "엔터"


def test_build_topic_lanes_twenty_discovery():
    lanes = build_topic_lanes(ISSUE_INDUSTRY_KEYS)
    assert len(lanes) == 20
    assert SOURCE_LANES == ("korea", "global")
    # Order: korea then global per industry
    assert lanes[0].industry_key == "politics"
    assert lanes[0].source_lane == "korea"
    assert lanes[1].source_lane == "global"
    for lane in lanes:
        assert "has:replies" not in lane.query
        if lane.source_lane == "korea":
            assert "lang:ko" in lane.query
        else:
            assert "lang:en" in lane.query


def test_select_topic_lanes_budget_eight_round_robin():
    lanes = build_topic_lanes(ISSUE_INDUSTRY_KEYS)
    selected, next_off = select_topic_lanes(lanes, budget=8, offset=0)
    assert len(selected) == 8
    assert next_off == 8
    labels = [f"{l.industry_key}/{l.source_lane}" for l in selected]
    assert labels == [
        "politics/korea",
        "politics/global",
        "economy/korea",
        "economy/global",
        "finance/korea",
        "finance/global",
        "tech/korea",
        "tech/global",
    ]
    selected_b, next_b = select_topic_lanes(lanes, budget=8, offset=next_off)
    assert len(selected_b) == 8
    assert next_b == 16
    selected_c, next_c = select_topic_lanes(lanes, budget=8, offset=next_b)
    assert len(selected_c) == 8
    assert next_c == 4  # wrap: 16,17,18,19,0,1,2,3 → next=4
    # Full coverage in 3 cycles
    seen = {f"{l.industry_key}/{l.source_lane}" for l in selected + selected_b + selected_c}
    assert len(seen) == 20


def test_topic_since_cursor_keys():
    assert topic_since_cursor_key("ai", "korea") == "topic:ai:korea:since_id"
    assert legacy_topic_since_cursor_key("ai") == "topic:ai:since_id"


def test_discovery_query_for_lanes():
    ko = discovery_query_for("ai", "korea")
    en = discovery_query_for("ai", "global")
    assert ko is not None and en is not None
    assert "lang:ko" in ko and "has:replies" not in ko
    assert "lang:en" in en and "has:replies" not in en

