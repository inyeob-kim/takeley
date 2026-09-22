"""RawItem upsert must tolerate duplicate content_fingerprint rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import RawItem
from app.db.repositories import RawItemRepository
from app.db.session import Base
from app.domain.models import RawItem as RawItemDomain, SourceType
from app.pipeline.normalize import content_fingerprint, normalize_text


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_upsert_many_survives_duplicate_fingerprints():
    db = _session()
    text = "Antitrust pressure on Big Tech isn't going away."
    fp = content_fingerprint(normalize_text(text))
    now = datetime.utcnow()
    # Legacy duplicate fingerprints (no unique constraint on fingerprint).
    for eid in ("dup-a", "dup-b"):
        db.add(
            RawItem(
                provider="x",
                external_id=eid,
                text=text,
                content_fingerprint=fp,
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        )
    db.commit()

    repo = RawItemRepository(db)
    inserted = repo.upsert_many(
        [
            RawItemDomain(
                provider=SourceType.X,
                external_id="dup-c",
                text=text,
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        ]
    )
    assert inserted == 0
    assert db.query(RawItem).count() == 2
