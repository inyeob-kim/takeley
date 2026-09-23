"""Issue Pipeline V2: candidate → understanding → match → card → gate → draft.

Lexical clustering is pregroup for cost only — LLM Match decides same-Issue.
Admin publish (draft → published) is required before home feed exposure.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.usage import (
    CANDIDATE_ACCEPTED,
    CANDIDATE_REJECTED,
    DUPLICATE_ISSUE_PREVENTED,
    ISSUE_CREATED,
    ISSUE_REJECTED,
    ISSUE_UPDATED,
    UNDERSTANDING_REJECTED,
    record_usage,
)
from app.db.models import Signal, SignalSource
from app.db.repositories import CursorRepository, EventRepository, RawItemRepository, SignalRepository
from app.domain.models import MarketSignal, SignalStatus
from app.pipeline.analyze import analyze_cluster
from app.pipeline.candidate import ScoredCandidate, priority_score, rank_for_pool
from app.pipeline.cheap_filter import cheap_filter_text
from app.pipeline.cluster import Cluster, ClusterItem, cluster_items
from app.pipeline.dynamic_query import arm_dynamic_topic, remember_topics
from app.pipeline.embeddings import rank_ids_by_embedding
from app.pipeline.evidence import trust_tier_for_provider
from app.pipeline.issue_heat import max_reply_count_from_payloads
from app.pipeline.issue_quality import passes_issue_quality_gate
from app.pipeline.matching import (
    DECISION_NEW,
    DECISION_REJECT,
    DECISION_UPDATE,
    ExistingIssueBrief,
    match_to_existing,
)
from app.pipeline.normalize import content_fingerprint, normalize_text
from app.pipeline.quality_judge import judge_issue_card
from app.pipeline.understanding import understand_candidate
from app.pipeline.velocity import compute_velocity, record_metric_snapshot
from app.services.issue_service import (
    apply_issue_fields,
    replace_participation_options,
    touch_content_updated,
)
from app.services.push_enqueue_service import enqueue_issue_update

logger = logging.getLogger(__name__)


def _attach_sources_v2(signal: Signal, cluster: Cluster, evidence: str | None) -> None:
    existing_urls = {s.url for s in (signal.sources or []) if s.url}
    existing_raw = {s.raw_item_id for s in (signal.sources or []) if s.raw_item_id}
    for item in cluster.items:
        if item.raw_id in existing_raw:
            continue
        if item.url and item.url in existing_urls:
            continue
        signal.sources.append(
            SignalSource(
                raw_item_id=item.raw_id,
                url=item.url,
                provider=item.provider,
                evidence_type=evidence,
                trust_tier=trust_tier_for_provider(item.provider),
            )
        )


def _recent_issue_shortlist(db: Session, *, limit: int) -> list[ExistingIssueBrief]:
    since = datetime.utcnow() - timedelta(days=5)
    rows = (
        db.query(Signal)
        .filter(
            Signal.status.in_(("draft", "published")),
            Signal.first_seen_at >= since,
        )
        .order_by(Signal.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ExistingIssueBrief(
            id=r.id,
            title=r.title or "",
            summary=r.summary or "",
            topic=r.topic or "",
            category=r.category,
        )
        for r in rows
    ]


def _metrics_from_payloads(payloads: list[dict | None]) -> dict[str, int]:
    likes = replies = rts = quotes = 0
    for payload in payloads:
        if not payload or not isinstance(payload, dict):
            continue
        m = payload.get("public_metrics") or payload.get("metrics") or {}
        if not isinstance(m, dict):
            continue
        likes = max(likes, int(m.get("like_count") or 0))
        replies = max(replies, int(m.get("reply_count") or 0))
        rts = max(rts, int(m.get("retweet_count") or 0))
        quotes = max(quotes, int(m.get("quote_count") or 0))
    return {
        "like_count": likes,
        "reply_count": replies,
        "retweet_count": rts,
        "quote_count": quotes,
    }


def _shortlist_for_match(
    db: Session,
    *,
    query_text: str,
    limit: int,
) -> list[ExistingIssueBrief]:
    """Build Match shortlist; embeddings may reorder (assist only)."""
    base = _recent_issue_shortlist(db, limit=max(limit * 2, limit))
    if len(base) <= 1:
        return base[:limit]
    pairs = [
        (e.id, f"{e.topic} {e.title} {e.summary}".strip()) for e in base
    ]
    ranked_ids = rank_ids_by_embedding(query_text, pairs, top_k=limit)
    by_id = {e.id: e for e in base}
    ordered = [by_id[i] for i in ranked_ids if i in by_id]
    if len(ordered) < limit:
        for e in base:
            if e.id not in {x.id for x in ordered}:
                ordered.append(e)
            if len(ordered) >= limit:
                break
    return ordered[:limit]


def _apply_velocity(db: Session, signal: Signal, payloads: list[dict | None]) -> None:
    from app.pipeline.trend_status import apply_trend_status

    metrics = _metrics_from_payloads(payloads)
    record_metric_snapshot(
        db,
        signal_id=signal.id,
        reply_count=metrics["reply_count"],
        like_count=metrics["like_count"],
        retweet_count=metrics["retweet_count"],
        quote_count=metrics["quote_count"],
    )
    reading = compute_velocity(db, signal.id)
    apply_trend_status(db, signal, velocity=reading)
    db.commit()


def _lane_tags(payloads: list) -> dict:
    tags: dict[str, str] = {}
    for payload in payloads or []:
        if not isinstance(payload, dict):
            continue
        if payload.get("issue_industry") and "industry" not in tags:
            tags["industry"] = str(payload["issue_industry"])
        if payload.get("source_lane") and "source_lane" not in tags:
            tags["source_lane"] = str(payload["source_lane"])
        if payload.get("scan_slot") and "scan_slot" not in tags:
            tags["scan_slot"] = str(payload["scan_slot"])
    return tags


def _lane_keys(payloads: list) -> set[str]:
    keys: set[str] = set()
    for payload in payloads or []:
        if not isinstance(payload, dict):
            continue
        industry = payload.get("issue_industry")
        lane = payload.get("source_lane")
        if industry and lane:
            keys.add(f"{industry}:{lane}")
    return keys


def run_process_issues_v2(db: Session, limit: int = 100) -> dict:
    settings = get_settings()
    raw_repo = RawItemRepository(db)
    signal_repo = SignalRepository(db)
    event_repo = EventRepository(db)

    rows = raw_repo.unprocessed(limit=limit)
    if not rows:
        return {
            "pipeline": "v2",
            "processed_raw": 0,
            "signals_created": 0,
            "signals_updated": 0,
            "signals_rejected": 0,
        }

    handled: list[str] = []
    scored: list[ScoredCandidate] = []
    cheap_dropped = 0

    for row in rows:
        text = normalize_text(row.text if not row.title else f"{row.title}. {row.text}")
        row.content_fingerprint = content_fingerprint(text)
        if len(text.strip()) < 8:
            handled.append(row.id)
            cheap_dropped += 1
            continue
        gate = cheap_filter_text(text)
        if not gate.accepted:
            cheap_dropped += 1
            handled.append(row.id)
            continue
        payload = row.raw_payload or {}
        decision = priority_score(
            provider=row.provider,
            published_at=row.published_at,
            payload=payload if isinstance(payload, dict) else {},
        )
        scored.append(
            ScoredCandidate(
                raw_id=row.id,
                text=text,
                url=row.url,
                provider=row.provider,
                published_at=row.published_at,
                payload=payload if isinstance(payload, dict) else {},
                priority_score=decision.priority_score,
                reasons=list(decision.reasons),
            )
        )

    db.commit()
    budget = settings.issue_llm_understand_budget_per_cycle
    reserve = False
    try:
        from app.services.x_ingest_admin import get_or_create as get_x_ingest_config

        x_config = get_x_ingest_config(db)
        budget = int(x_config.understand_budget or budget)
        reserve = bool(x_config.industry_slot_reserve)
    except Exception:
        logger.exception("x ingest config unavailable; using env understand budget")
    if reserve:
        from app.pipeline.candidate import rank_for_pool_reserved

        pool = rank_for_pool_reserved(scored, budget=budget)
    else:
        pool = rank_for_pool(scored, budget=budget)
    pool_ids = {c.raw_id for c in pool}
    # Candidates not in Top-N stay unprocessed for a later cycle (cost control).
    for c in scored:
        if c.raw_id not in pool_ids:
            record_usage(CANDIDATE_REJECTED, 1, db=db, tags={"reason": "budget"})

    record_usage(CANDIDATE_ACCEPTED, len(pool), db=db)

    # Pregroup is COST ONLY — not final same-Issue judgment (see matching.py).
    cluster_items_list = [
        ClusterItem(
            raw_id=c.raw_id,
            text=c.text,
            url=c.url,
            provider=c.provider,
            published_at=c.published_at,
        )
        for c in pool
    ]
    pregroups = cluster_items(cluster_items_list, similarity=0.90)
    payload_by_id = {c.raw_id: c.payload for c in pool}

    created = 0
    updated = 0
    rejected = 0
    _meaningful: set[str] = set()
    remembered_topics: list[str] = []
    armed_topics: list[tuple[str, str, str]] = []

    for pregroup in pregroups:
        # Representative: highest priority member
        rep_id = pregroup.raw_ids[0]
        rep = next((c for c in pool if c.raw_id == rep_id), None)
        if not rep:
            continue
        understanding = understand_candidate(
            text=rep.text,
            provider=rep.provider,
            raw_id=rep.raw_id,
        )
        for rid in pregroup.raw_ids:
            handled.append(rid)

        if understanding.topic:
            remembered_topics.append(understanding.topic)

        if not understanding.is_issue_candidate:
            rejected += 1
            record_usage(UNDERSTANDING_REJECTED, 1, db=db)
            continue

        if understanding.topic:
            origin = payload_by_id.get(rep.raw_id) or {}
            armed_topics.append(
                (
                    understanding.topic,
                    str(origin.get("issue_industry") or "dynamic"),
                    str(origin.get("source_lane") or "global"),
                )
            )

        query_blob = " ".join(
            [
                understanding.topic,
                understanding.event,
                understanding.claim,
                " ".join(understanding.entities),
            ]
        )
        shortlist = _shortlist_for_match(
            db,
            query_text=query_blob or rep.text[:500],
            limit=settings.issue_llm_match_shortlist,
        )

        match = match_to_existing(understanding, shortlist)
        if match.decision == DECISION_REJECT:
            rejected += 1
            record_usage(ISSUE_REJECTED, 1, db=db, tags={"reason": match.reason})
            continue

        payloads = [payload_by_id.get(rid) for rid in pregroup.raw_ids]

        if match.decision == DECISION_UPDATE and match.existing_issue_id:
            existing = (
                db.query(Signal)
                .filter(
                    Signal.id == match.existing_issue_id,
                    Signal.status.in_(("draft", "published")),
                )
                .first()
            )
            if existing:
                _attach_sources_v2(existing, pregroup, None)
                existing.lifecycle = "UPDATED"
                existing.updated_at = datetime.utcnow()
                # Semantic UPDATE (new evidence) — retention clock, not ORM updated_at.
                touch_content_updated(existing)
                reply_peak = max_reply_count_from_payloads(payloads)
                if reply_peak:
                    existing.source_reply_peak = max(
                        int(existing.source_reply_peak or 0), reply_peak
                    )
                db.commit()
                _apply_velocity(db, existing, payloads)
                updated += 1
                _meaningful |= _lane_keys(payloads)
                record_usage(
                    ISSUE_UPDATED,
                    1,
                    db=db,
                    tags=_lane_tags(payloads),
                )
                record_usage(DUPLICATE_ISSUE_PREVENTED, 1, db=db)
                try:
                    enqueue_issue_update(
                        db, signal_id=existing.id, title=existing.title or ""
                    )
                except Exception:
                    logger.exception(
                        "issue_update push failed after UPDATE signal=%s", existing.id
                    )
                continue

        # NEW_ISSUE → structure card via existing analyze_cluster on pregroup
        domain = analyze_cluster(pregroup, universe_symbols=[])
        reply_peak = max_reply_count_from_payloads(payloads)
        domain.source_reply_peak = reply_peak
        if not domain.topic and understanding.topic:
            domain.topic = understanding.topic[:120]
        if understanding.entities and not domain.related_symbols:
            domain.related_sectors = list(
                dict.fromkeys(
                    (domain.related_sectors or []) + understanding.entities[:4]
                )
            )

        q = passes_issue_quality_gate(domain, source_count=len(pregroup.items))
        if not q.accepted:
            rejected += 1
            record_usage(ISSUE_REJECTED, 1, db=db, tags={"reason": q.reason})
            continue

        judge = judge_issue_card(
            domain, evidence_text="\n".join(pregroup.texts)
        )
        if not judge.accepted:
            rejected += 1
            record_usage(
                ISSUE_REJECTED, 1, db=db, tags={"reason": f"judge:{judge.reason}"}
            )
            continue

        published_today = signal_repo.count_issue_cards_today()
        soft_cap = settings.effective_daily_issue_soft_cap()
        if published_today >= settings.daily_signal_hard_ceiling:
            rejected += 1
            logger.info(
                "issue hard ceiling reached published=%s hard=%s",
                published_today,
                settings.daily_signal_hard_ceiling,
            )
            continue
        if published_today >= soft_cap:
            if float(domain.importance or 0) < settings.priority_importance_threshold:
                logger.info(
                    "issue soft cap defer title=%s importance=%s",
                    (domain.title or "")[:60],
                    domain.importance,
                )
                rejected += 1
                continue

        event = event_repo.upsert_from_cluster(
            cluster_key=pregroup.key,
            title=domain.title,
            related_symbols=domain.related_symbols,
            related_sectors=domain.related_sectors,
            providers=pregroup.unique_providers,
            raw_ids=pregroup.raw_ids,
        )

        existing_same_event = (
            db.query(Signal)
            .filter(
                Signal.event_id == event.id,
                Signal.status.in_(("draft", "published")),
            )
            .order_by(Signal.updated_at.desc())
            .first()
        )
        if existing_same_event:
            apply_issue_fields(existing_same_event, domain, db=db)
            _attach_sources_v2(existing_same_event, pregroup, None)
            existing_same_event.lifecycle = "UPDATED"
            existing_same_event.updated_at = datetime.utcnow()
            touch_content_updated(existing_same_event)
            if domain.participation_suitable and domain.participation_options:
                replace_participation_options(
                    db, existing_same_event, domain.participation_options
                )
            db.commit()
            _apply_velocity(db, existing_same_event, payloads)
            updated += 1
            record_usage(DUPLICATE_ISSUE_PREVENTED, 1, db=db)
            try:
                enqueue_issue_update(
                    db,
                    signal_id=existing_same_event.id,
                    title=existing_same_event.title or "",
                )
            except Exception:
                logger.exception(
                    "issue_update push failed after UPDATE signal=%s",
                    existing_same_event.id,
                )
            continue

        evidence = domain.evidence_mix[0].value if domain.evidence_mix else None
        # Admin review gate: never auto-publish to the home feed.
        signal = Signal(
            event_id=event.id,
            title=domain.title,
            summary=domain.summary,
            why_it_matters=domain.why_it_matters,
            column_body=getattr(domain, "column_body", "") or "",
            confirmed_facts=domain.confirmed_facts,
            key_points=domain.key_points,
            emphasis=domain.emphasis or {},
            market_reaction=domain.market_reaction,
            evidence_mix=[e.value for e in domain.evidence_mix],
            content_type=domain.content_type,
            evidence_level=domain.evidence_level,
            importance=domain.importance,
            confidence=domain.confidence,
            related_symbols=domain.related_symbols,
            related_sectors=domain.related_sectors,
            cluster_key=pregroup.key,
            status=SignalStatus.DRAFT.value,
            first_seen_at=domain.first_seen_at,
            published_at=None,
            updated_at=domain.updated_at,
            content_updated_at=domain.first_seen_at or datetime.utcnow(),
            lifecycle="CANDIDATE",
            trend_status="NORMAL",
        )
        apply_issue_fields(signal, domain, db=db)
        signal.status = SignalStatus.DRAFT.value
        _attach_sources_v2(signal, pregroup, evidence)
        signal_repo.save(signal)
        if domain.participation_suitable and domain.participation_options:
            replace_participation_options(db, signal, domain.participation_options)
            db.commit()
        _apply_velocity(db, signal, payloads)
        created += 1
        _meaningful |= _lane_keys(payloads)
        record_usage(ISSUE_CREATED, 1, db=db, tags=_lane_tags(payloads))
        # Push / feed exposure waits for admin publish — no ISSUE_PUBLISHED / enqueue.

    if remembered_topics:
        remember_topics(CursorRepository(db), remembered_topics)
    if armed_topics:
        cursors = CursorRepository(db)
        for topic, industry, lane in armed_topics:
            arm_dynamic_topic(
                cursors,
                topic=topic,
                industry=industry,
                source_lane=lane,
            )

    raw_repo.mark_processed(list(dict.fromkeys(handled)))
    cards_today = signal_repo.count_issue_cards_today()
    result = {
        "pipeline": "issue",
        "processed_raw": len(handled),
        "pool_size": len(pool),
        "pregroups": len(pregroups),
        "signals_created": created,
        "signals_updated": updated,
        "signals_rejected": rejected,
        "meaningful_lanes": sorted(_meaningful),
        "cheap_filter_dropped": cheap_dropped,
        "published_today": cards_today,
        "quota_remaining": max(
            0, settings.effective_daily_issue_soft_cap() - cards_today
        ),
    }
    logger.info("process_issues %s", result)
    return result
