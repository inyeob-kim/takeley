"""Extra coverage for velocity, embeddings assist, dynamic query, quality judge."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import MetricSnapshot, Signal
from app.db.session import Base
from app.db.repositories import CursorRepository
from app.domain.models import MarketSignal
from app.pipeline.dynamic_query import dynamic_search_queries, remember_topics
from app.pipeline.embeddings import rank_ids_by_embedding
from app.pipeline.quality_judge import judge_issue_card
from app.pipeline.velocity import compute_velocity, record_metric_snapshot


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_velocity_rising_from_snapshots():
    db = _session()
    sig = Signal(title="t", summary="s", status="published")
    db.add(sig)
    db.commit()
    db.refresh(sig)
    t0 = datetime.utcnow() - timedelta(hours=2)
    db.add(
        MetricSnapshot(
            signal_id=sig.id,
            reply_count=2,
            like_count=10,
            engagement_score=16.0,
            captured_at=t0,
        )
    )
    db.commit()
    record_metric_snapshot(db, signal_id=sig.id, reply_count=40, like_count=100)
    reading = compute_velocity(db, sig.id)
    assert reading.reply_velocity > 0
    assert reading.trend_status in {"RISING", "TRENDING", "NORMAL"}


def test_dynamic_query_remember_and_build():
    db = _session()
    repo = CursorRepository(db)
    remember_topics(repo, ["Blackwell demand surge", "x"])
    qs = dynamic_search_queries(repo, budget=2)
    assert qs
    assert "has:replies" not in qs[0]
    assert "lang:en" in qs[0]


def test_embedding_rank_fallback_without_api():
    ids = rank_ids_by_embedding(
        "nvidia blackwell",
        [("a", "nvidia blackwell demand"), ("b", "unrelated cats")],
        top_k=1,
    )
    assert len(ids) == 1
    assert ids[0] in {"a", "b"}


def test_quality_judge_rejects_promo_heuristic():
    sig = MarketSignal(
        title="Buy TSLA now tipster call",
        summary="This is a promotional investment call tipster spam content here.",
        why_it_matters="n/a",
        content_type="INVESTMENT_CALL",
    )
    d = judge_issue_card(sig)
    assert d.accepted is False
    assert d.source in {"heuristic", "llm", "skipped"}
