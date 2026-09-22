from app.pipeline.issue_heat import (
    engagement_score,
    max_reply_count_from_payloads,
    pick_hottest,
    topic_heat_decision,
)


def test_engagement_weights_replies_higher():
    assert engagement_score({"like_count": 10, "reply_count": 0}) == 10
    assert engagement_score({"like_count": 0, "reply_count": 5}) == 15


def test_cold_without_replies_dropped():
    d = topic_heat_decision(
        metrics={"like_count": 100, "reply_count": 0},
        min_score=15,
        min_replies=5,
    )
    assert d.accepted is False
    assert d.reason == "cold_engagement"


def test_reply_threshold_passes():
    d = topic_heat_decision(
        metrics={"like_count": 2, "reply_count": 6},
        min_score=15,
        min_replies=5,
    )
    assert d.accepted is True
    assert d.reply_count == 6


def test_hot_replies_and_score():
    d = topic_heat_decision(
        metrics={"like_count": 20, "reply_count": 5, "retweet_count": 3},
        min_score=15,
        min_replies=5,
    )
    assert d.accepted is True


def test_pick_hottest_orders_by_replies():
    class _Item:
        def __init__(self, likes, replies):
            self.text = "x"
            self.raw_payload = {
                "public_metrics": {"like_count": likes, "reply_count": replies}
            }

    items = [
        _Item(100, 5),
        _Item(5, 20),
        _Item(50, 1),
    ]
    hot = pick_hottest(items, limit=2, min_score=10, min_replies=5)
    assert len(hot) == 2
    assert hot[0].raw_payload["public_metrics"]["reply_count"] == 20


def test_max_reply_peak():
    assert (
        max_reply_count_from_payloads(
            [
                {"public_metrics": {"reply_count": 3}},
                {"public_metrics": {"reply_count": 12}},
                None,
            ]
        )
        == 12
    )
