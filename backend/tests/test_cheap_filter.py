from app.pipeline.cheap_filter import cheap_filter_text


def test_cheap_filter_accepts_normal_news():
    text = (
        "Tesla raised vehicle prices in several European markets after "
        "delivery data showed softer demand last quarter."
    )
    decision = cheap_filter_text(text)
    assert decision.accepted
    assert decision.reason == "ok"


def test_cheap_filter_drops_url_only():
    decision = cheap_filter_text("https://t.co/abcdefg https://x.com/foo")
    assert not decision.accepted
    assert decision.reason in ("url_only", "too_short")


def test_cheap_filter_drops_engagement_junk():
    decision = cheap_filter_text(
        "Follow me for daily TSLA tips and retweet this giveaway link please!!!"
    )
    assert not decision.accepted
    assert decision.reason == "engagement_junk"


def test_cheap_filter_drops_too_short():
    decision = cheap_filter_text("TSLA up")
    assert not decision.accepted
    assert decision.reason == "too_short"
