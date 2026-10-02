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


def test_upsert_many_skips_existing_and_batch_duplicate_keys():
    db = _session()
    now = datetime.utcnow()
    db.add(
        RawItem(
            provider="official",
            external_id="urn:sec:already",
            text="Existing SEC filing body.",
            content_fingerprint="fp-existing",
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
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:already",
                text="Existing SEC filing body.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            ),
            RawItemDomain(
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:new",
                text="Brand new SEC filing body for insert.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            ),
            # Same key twice in one batch — only one insert.
            RawItemDomain(
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:new",
                text="Brand new SEC filing body for insert.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            ),
        ]
    )
    assert inserted == 1
    assert db.query(RawItem).filter(RawItem.provider == "official").count() == 2
    # Session remains usable after dup handling.
    assert repo.upsert_many([]) == 0


def test_upsert_many_integrity_race_does_not_poison_session():
    """Simulate unique hit after the pre-check (e.g. concurrent insert)."""
    db = _session()
    now = datetime.utcnow()
    repo = RawItemRepository(db)

    first = repo.upsert_many(
        [
            RawItemDomain(
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:race",
                text="First write of the SEC accession.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        ]
    )
    assert first == 1
    second = repo.upsert_many(
        [
            RawItemDomain(
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:race",
                text="First write of the SEC accession.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        ]
    )
    assert second == 0
    # Follow-up write still works (session not stuck in PendingRollback).
    third = repo.upsert_many(
        [
            RawItemDomain(
                provider=SourceType.OFFICIAL,
                external_id="urn:sec:after-race",
                text="Another filing after the duplicate attempt.",
                fetched_at=now,
                published_at=now,
                raw_payload={},
            )
        ]
    )
    assert third == 1
