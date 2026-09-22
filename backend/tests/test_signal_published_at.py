from datetime import datetime, timedelta

from app.pipeline.cluster import Cluster, ClusterItem


def test_earliest_published_at_picks_min():
    early = datetime(2026, 9, 16, 8, 0, 0)
    late = datetime(2026, 9, 16, 12, 0, 0)
    cluster = Cluster(
        key="k",
        items=[
            ClusterItem("1", "a", published_at=late),
            ClusterItem("2", "b", published_at=early),
            ClusterItem("3", "c", published_at=None),
        ],
    )
    assert cluster.earliest_published_at == early


def test_earliest_published_at_none_when_missing():
    cluster = Cluster(key="k", items=[ClusterItem("1", "a")])
    assert cluster.earliest_published_at is None


def test_heuristic_uses_source_published_at():
    from app.pipeline.analyze import _heuristic_analyze

    published = datetime.utcnow() - timedelta(hours=3)
    cluster = Cluster(
        key="k",
        texts=["Tesla raises deliveries in Q3 report"],
        items=[
            ClusterItem(
                "1",
                "Tesla raises deliveries in Q3 report",
                provider="news",
                published_at=published,
            )
        ],
        providers=["news"],
    )
    signal = _heuristic_analyze(cluster)
    assert signal.published_at == published
