"""Issue feed + participation (Signals table as Issue store)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.models import (
    IssueComment,
    IssueFollow,
    IssueUserEvent,
    IssueView,
    Participation,
    ParticipationOption,
    RawItem,
    Signal,
    User,
)
from app.schemas import (
    IssueCommentOut,
    IssueListOut,
    IssueOut,
    IssueSourceOut,
    MyActivityOut,
    ParticipationOptionOut,
)
from app.services.columnist_service import profile_is_public


def touch_content_updated(signal: Signal, when: datetime | None = None) -> None:
    """Bump semantic content time only (never for impression/open counters)."""
    signal.content_updated_at = when or datetime.utcnow()


_DATETIME_MIN = datetime(1970, 1, 1)


def _published_at_key(signal: Signal) -> datetime:
    return signal.published_at or signal.first_seen_at or _DATETIME_MIN


def _trending_rank_key(signal: Signal) -> tuple:
    """Higher = more trending. Prefer TRENDING/RISING, then trend_score."""
    status = (getattr(signal, "trend_status", None) or "NORMAL").upper()
    status_rank = {"TRENDING": 2, "RISING": 1}.get(status, 0)
    if bool(getattr(signal, "is_trending", False)) and status_rank < 2:
        status_rank = 2
    return (
        status_rank,
        float(signal.trend_score or 0.0),
        float(signal.importance or 0.0),
        int(signal.open_count or 0),
        _published_at_key(signal),
    )


def order_home_feed(rows: list[Signal], *, limit: int) -> list[Signal]:
    """Pin the single most-trending Issue, then order the rest by published_at desc.

    Used for 전체 and per-industry home chips (same rule within the filtered set).
    """
    if not rows or limit <= 0:
        return []
    featured = max(rows, key=_trending_rank_key)
    rest = [r for r in rows if r.id != featured.id]
    rest.sort(key=_published_at_key, reverse=True)
    return [featured, *rest][:limit]


def _user_display_names(db: Session, user_ids: list[str]) -> dict[str, str | None]:
    ids = list({uid for uid in user_ids if uid})
    if not ids:
        return {}
    rows = (
        db.query(User.id, User.display_name)
        .filter(User.id.in_(ids))
        .all()
    )
    out: dict[str, str | None] = {}
    for uid, name in rows:
        cleaned = (name or "").strip()
        out[uid] = cleaned or None
    return out


def _comment_out(
    row: IssueComment,
    *,
    display_name: str | None = None,
    issue_title: str = "",
) -> IssueCommentOut:
    return IssueCommentOut(
        id=row.id,
        issue_id=row.signal_id,
        user_id=row.user_id,
        content=row.content,
        like_count=int(row.like_count or 0),
        created_at=row.created_at,
        display_name=display_name,
        issue_title=issue_title or "",
    )


@dataclass
class _RetentionCtx:
    follow: IssueFollow | None = None
    participation: Participation | None = None
    view: IssueView | None = None


def _load_retention_maps(
    db: Session, user_id: str | None, signal_ids: list[str]
) -> dict[str, _RetentionCtx]:
    out: dict[str, _RetentionCtx] = {sid: _RetentionCtx() for sid in signal_ids}
    if not user_id or not signal_ids:
        return out
    for row in (
        db.query(IssueFollow)
        .filter(IssueFollow.user_id == user_id, IssueFollow.signal_id.in_(signal_ids))
        .all()
    ):
        out[row.signal_id].follow = row
    for row in (
        db.query(Participation)
        .filter(
            Participation.user_id == user_id, Participation.signal_id.in_(signal_ids)
        )
        .all()
    ):
        out[row.signal_id].participation = row
    for row in (
        db.query(IssueView)
        .filter(IssueView.user_id == user_id, IssueView.signal_id.in_(signal_ids))
        .all()
    ):
        out[row.signal_id].view = row
    return out


def _compute_has_new_update(
    signal: Signal, ctx: _RetentionCtx | None
) -> tuple[bool, datetime | None, bool]:
    """Return (has_new_update, my_last_seen_at, is_following)."""
    if not ctx:
        return False, None, False
    is_following = ctx.follow is not None
    last_seen = ctx.view.last_seen_at if ctx.view else None
    starts: list[datetime] = []
    if ctx.follow and ctx.follow.created_at:
        starts.append(ctx.follow.created_at)
    if ctx.participation and ctx.participation.created_at:
        starts.append(ctx.participation.created_at)
    if not starts:
        return False, last_seen, is_following
    interest_started_at = min(starts)
    content_at = getattr(signal, "content_updated_at", None)
    if not content_at:
        return False, last_seen, is_following
    if last_seen:
        return bool(content_at > last_seen), last_seen, is_following
    return bool(content_at > interest_started_at), last_seen, is_following


def _append_user_event(
    db: Session,
    *,
    user_id: str,
    signal_id: str | None,
    event: str,
    take_id: str | None = None,
    share_id: str | None = None,
    ref_user_id: str | None = None,
    share_intent: str | None = None,
) -> None:
    db.add(
        IssueUserEvent(
            user_id=user_id,
            signal_id=signal_id,
            take_id=take_id,
            share_id=(share_id or None),
            ref_user_id=(ref_user_id or None),
            share_intent=(share_intent or None),
            event=event,
            created_at=datetime.utcnow(),
        )
    )


def _excerpt(
    raw: RawItem | None, *, max_chars: int = 720
) -> tuple[str | None, str | None, str | None]:
    """title, excerpt, author — longer excerpt for detail columns."""
    if not raw:
        return None, None, None
    title = (raw.title or "").strip() or None
    author = (raw.author or "").strip() or None
    body = (raw.text or "").strip()
    if not body:
        return title, title, author
    excerpt = body if len(body) <= max_chars else f"{body[: max_chars - 1].rstrip()}…"
    return title, excerpt, author


def _compose_column_fallback(
    signal: Signal, source_excerpts: list[str]
) -> str:
    """Readable column when worker has not yet written column_body.

    Do not prepend summary — the client already shows summary above the body.
    """
    parts: list[str] = []
    summary = (signal.summary or "").strip()
    why = (signal.why_it_matters or "").strip()
    if why and why != summary:
        parts.append(why)
    points = [str(p).strip() for p in (signal.key_points or []) if str(p).strip()]
    if points:
        parts.append(
            "핵심만 정리하면 이래요.\n" + "\n".join(f"· {p}" for p in points[:5])
        )
    for ex in source_excerpts[:2]:
        text = (ex or "").strip()
        if text and text not in summary and text != why:
            parts.append(text)
    return "\n\n".join(parts)


def _option_counts(db: Session, signal_id: str) -> dict[str, int]:
    rows = (
        db.query(Participation.option_id, func.count(Participation.id))
        .filter(Participation.signal_id == signal_id)
        .group_by(Participation.option_id)
        .all()
    )
    return {oid: int(n) for oid, n in rows}


def _bulk_option_counts(
    db: Session, signal_ids: list[str]
) -> dict[str, dict[str, int]]:
    if not signal_ids:
        return {}
    rows = (
        db.query(
            Participation.signal_id,
            Participation.option_id,
            func.count(Participation.id),
        )
        .filter(Participation.signal_id.in_(signal_ids))
        .group_by(Participation.signal_id, Participation.option_id)
        .all()
    )
    out: dict[str, dict[str, int]] = {sid: {} for sid in signal_ids}
    for sid, oid, n in rows:
        out.setdefault(sid, {})[oid] = int(n)
    return out


def _bulk_comment_counts(db: Session, signal_ids: list[str]) -> dict[str, int]:
    if not signal_ids:
        return {}
    rows = (
        db.query(IssueComment.signal_id, func.count(IssueComment.id))
        .filter(
            IssueComment.signal_id.in_(signal_ids),
            IssueComment.status == "visible",
        )
        .group_by(IssueComment.signal_id)
        .all()
    )
    return {sid: int(n) for sid, n in rows}


def _public_columnist_id(signal: Signal) -> str | None:
    """Omit the profile link when the columnist turned the page off."""
    columnist_id = getattr(signal, "columnist_id", None) or None
    if not columnist_id:
        return None
    if profile_is_public(getattr(signal, "columnist", None)):
        return columnist_id
    return None


def _to_issue_out(
    db: Session,
    signal: Signal,
    *,
    user_id: str | None = None,
    include_sources: bool = False,
    expose_sources: bool | None = None,
    keep_columnist_link: bool = False,
    retention: _RetentionCtx | None = None,
    option_counts: dict[str, int] | None = None,
    comment_count: int | None = None,
) -> IssueOut:
    options = sorted(
        signal.participation_options or [],
        key=lambda o: (o.display_order, o.created_at or datetime.utcnow()),
    )
    counts = (
        option_counts if option_counts is not None else _option_counts(db, signal.id)
    )
    total = sum(counts.values())

    ctx = retention
    if ctx is None and user_id:
        maps = _load_retention_maps(db, user_id, [signal.id])
        ctx = maps.get(signal.id)

    my_option_id = None
    if ctx and ctx.participation:
        my_option_id = ctx.participation.option_id

    has_new, my_last_seen, is_following = _compute_has_new_update(signal, ctx)

    option_outs = [
        ParticipationOptionOut(
            id=o.id,
            label=o.label,
            display_order=o.display_order,
            count=counts.get(o.id, 0),
        )
        for o in options
    ]

    show_sources = bool(getattr(signal, "show_sources", False))
    # Admin can force-expose sources even when consumer flag is off.
    should_expose = include_sources and (
        show_sources if expose_sources is None else expose_sources
    )

    from app.services.push_copy import build_signal_new_copy

    push_copy = build_signal_new_copy(signal)

    sources_out: list[IssueSourceOut] = []
    source_excerpts: list[str] = []
    if include_sources:
        raw_ids = [s.raw_item_id for s in (signal.sources or []) if s.raw_item_id]
        raws = {}
        if raw_ids:
            raws = {
                r.id: r for r in db.query(RawItem).filter(RawItem.id.in_(raw_ids)).all()
            }
        for s in signal.sources or []:
            title, excerpt, author = _excerpt(
                raws.get(s.raw_item_id) if s.raw_item_id else None
            )
            if excerpt:
                source_excerpts.append(excerpt)
            if should_expose:
                sources_out.append(
                    IssueSourceOut(
                        id=s.id,
                        url=s.url,
                        provider=s.provider,
                        title=title,
                        excerpt=excerpt,
                        author=author,
                    )
                )

    column_body = (getattr(signal, "column_body", None) or "").strip()
    if include_sources and len(column_body) < 120:
        column_body = _compose_column_fallback(signal, source_excerpts)
    elif not column_body:
        column_body = _compose_column_fallback(signal, [])

    if comment_count is None:
        comment_count = int(
            db.query(func.count(IssueComment.id))
            .filter(
                IssueComment.signal_id == signal.id,
                IssueComment.status == "visible",
            )
            .scalar()
            or 0
        )

    published_at = signal.published_at or signal.first_seen_at
    trend = float(signal.trend_score or 0.0)
    if trend <= 0:
        trend = float(signal.importance or 0.0)

    raw_source_count = len(signal.sources or [])
    public_source_count = raw_source_count if show_sources else 0

    return IssueOut(
        id=signal.id,
        title=signal.title,
        summary=signal.summary,
        why_it_matters=signal.why_it_matters or "",
        column_body=column_body,
        image_url=(getattr(signal, "image_url", None) or None),
        column_author_name=(
            (getattr(signal, "column_author_name", None) or "").strip() or None
        ),
        column_author_image_url=(
            getattr(signal, "column_author_image_url", None) or None
        ),
        columnist_id=(
            (getattr(signal, "columnist_id", None) or None)
            if keep_columnist_link
            else _public_columnist_id(signal)
        ),
        key_points=signal.key_points or [],
        category=signal.category,
        topic=signal.topic,
        trend_score=trend,
        is_trending=bool(getattr(signal, "is_trending", False)),
        trend_status=(getattr(signal, "trend_status", None) or "NORMAL"),
        importance=float(signal.importance or 0.5),
        confidence=float(signal.confidence or 0.5),
        content_type=signal.content_type or "REPORT",
        evidence_level=signal.evidence_level or "UNVERIFIED",
        related_symbols=signal.related_symbols or [],
        participation_suitable=bool(signal.participation_suitable),
        participation_type=signal.participation_type,
        participation_question=signal.participation_question,
        show_sources=show_sources,
        push_title=(getattr(signal, "push_title", None) or None),
        push_body=(getattr(signal, "push_body", None) or None),
        push_preview_title=push_copy.title,
        push_preview_body=push_copy.body,
        push_kind=push_copy.kind,
        options=option_outs,
        participation_count=total,
        my_option_id=my_option_id,
        source_count=public_source_count if expose_sources is None else raw_source_count,
        sources=sources_out,
        comment_count=int(comment_count),
        impression_count=int(signal.impression_count or 0),
        open_count=int(signal.open_count or 0),
        status=signal.status,
        published_at=published_at,
        first_seen_at=signal.first_seen_at,
        updated_at=signal.updated_at,
        content_updated_at=getattr(signal, "content_updated_at", None),
        is_following=is_following,
        has_new_update=has_new,
        my_last_seen_at=my_last_seen,
    )


class IssueService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def list_issues(
        self,
        *,
        limit: int = 20,
        sort: str = "trending",
        category: str | None = None,
        q: str | None = None,
        user_id: str | None = None,
    ) -> IssueListOut:
        from app.pipeline.industries import (
            all_industry_labels,
            category_filter_values,
        )
        from sqlalchemy import or_

        limit = max(1, min(limit, 50))
        industry_labels = all_industry_labels()
        query = (
            self.db.query(Signal)
            .options(
                joinedload(Signal.participation_options), joinedload(Signal.sources)
            )
            .filter(Signal.status == "published")
            .filter(
                or_(
                    Signal.category.in_(industry_labels),
                    Signal.participation_suitable.is_(True),
                    Signal.topic.isnot(None),
                    Signal.is_trending.is_(True),
                )
            )
        )
        cat_values = category_filter_values(category)
        if cat_values:
            query = query.filter(Signal.category.in_(cat_values))

        needle = (q or "").strip()
        if needle:
            if len(needle) > 40:
                needle = needle[:40]
            like = f"%{needle}%"
            query = query.filter(
                or_(
                    Signal.title.ilike(like),
                    Signal.summary.ilike(like),
                    Signal.why_it_matters.ilike(like),
                )
            )

        if sort == "new":
            query = query.order_by(Signal.first_seen_at.desc())
            rows = query.limit(limit).all()
        elif sort == "rising":
            query = query.order_by(
                Signal.open_count.desc(),
                Signal.importance.desc(),
                Signal.first_seen_at.desc(),
            )
            rows = query.limit(limit).all()
        else:
            # Home: 1 most-trending pinned, remainder by publish time (전체 + 산업).
            pool_cap = max(limit * 10, 100)
            pool = query.order_by(
                Signal.trend_score.desc(),
                Signal.importance.desc(),
                Signal.first_seen_at.desc(),
            ).limit(pool_cap).all()
            rows = order_home_feed(pool, limit=limit)
        ids = [s.id for s in rows]
        retention = _load_retention_maps(self.db, user_id, ids)
        opt_counts = _bulk_option_counts(self.db, ids)
        comment_counts = _bulk_comment_counts(self.db, ids)
        items = [
            _to_issue_out(
                self.db,
                s,
                user_id=user_id,
                include_sources=False,
                retention=retention.get(s.id),
                option_counts=opt_counts.get(s.id, {}),
                comment_count=comment_counts.get(s.id, 0),
            )
            for s in rows
        ]
        return IssueListOut(items=items, count=len(items))

    def get_issue(self, issue_id: str, *, user_id: str | None = None) -> IssueOut | None:
        row = (
            self.db.query(Signal)
            .options(
                joinedload(Signal.participation_options), joinedload(Signal.sources)
            )
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not row:
            return None
        return _to_issue_out(self.db, row, user_id=user_id, include_sources=True)

    def record_view(self, issue_id: str, *, user_id: str) -> IssueOut | None:
        signal = (
            self.db.query(Signal)
            .options(joinedload(Signal.participation_options))
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not signal:
            return None
        now = datetime.utcnow()
        view = (
            self.db.query(IssueView)
            .filter(IssueView.user_id == user_id, IssueView.signal_id == issue_id)
            .first()
        )
        had_update = False
        maps = _load_retention_maps(self.db, user_id, [issue_id])
        ctx = maps.get(issue_id) or _RetentionCtx()
        had_update, _, _ = _compute_has_new_update(signal, ctx)
        if view:
            view.last_seen_at = now
        else:
            view = IssueView(
                user_id=user_id,
                signal_id=issue_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(view)
        signal.open_count = int(signal.open_count or 0) + 1
        _append_user_event(self.db, user_id=user_id, signal_id=issue_id, event="open")
        if had_update:
            _append_user_event(
                self.db, user_id=user_id, signal_id=issue_id, event="update_seen"
            )
        from app.pipeline.trend_status import apply_trend_status

        apply_trend_status(self.db, signal)
        self.db.commit()
        return _to_issue_out(self.db, signal, user_id=user_id)

    def follow(self, issue_id: str, *, user_id: str) -> IssueOut | None:
        signal = (
            self.db.query(Signal)
            .options(joinedload(Signal.participation_options))
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not signal:
            return None
        existing = (
            self.db.query(IssueFollow)
            .filter(IssueFollow.user_id == user_id, IssueFollow.signal_id == issue_id)
            .first()
        )
        if not existing:
            self.db.add(
                IssueFollow(
                    user_id=user_id,
                    signal_id=issue_id,
                    created_at=datetime.utcnow(),
                )
            )
            _append_user_event(
                self.db, user_id=user_id, signal_id=issue_id, event="follow"
            )
            from app.pipeline.trend_status import apply_trend_status

            apply_trend_status(self.db, signal)
            self.db.commit()
        return _to_issue_out(self.db, signal, user_id=user_id)

    def unfollow(self, issue_id: str, *, user_id: str) -> IssueOut | None:
        signal = (
            self.db.query(Signal)
            .options(joinedload(Signal.participation_options))
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not signal:
            return None
        existing = (
            self.db.query(IssueFollow)
            .filter(IssueFollow.user_id == user_id, IssueFollow.signal_id == issue_id)
            .first()
        )
        if existing:
            self.db.delete(existing)
            _append_user_event(
                self.db, user_id=user_id, signal_id=issue_id, event="unfollow"
            )
            from app.pipeline.trend_status import apply_trend_status

            apply_trend_status(self.db, signal)
            self.db.commit()
        return _to_issue_out(self.db, signal, user_id=user_id)

    def record_event(
        self,
        issue_id: str,
        event: str,
        *,
        user_id: str | None = None,
        share_id: str | None = None,
        ref_user_id: str | None = None,
        share_intent: str | None = None,
    ) -> dict | None:
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        if not row:
            return None
        share_events = {
            "share_clicked",
            "share_completed",
            "share_cancelled",
            "share_link_copied",
            "shared_link_opened",
            "store_click",
        }
        # impression: counters only — never IssueView / content_updated_at
        if event == "impression":
            row.impression_count = int(row.impression_count or 0) + 1
            if user_id:
                _append_user_event(
                    self.db,
                    user_id=user_id,
                    signal_id=issue_id,
                    event="impression",
                    share_id=share_id,
                    ref_user_id=ref_user_id,
                    share_intent=share_intent,
                )
            self.db.commit()
        elif event == "open":
            if user_id:
                self.record_view(issue_id, user_id=user_id)
                row = self.db.query(Signal).filter(Signal.id == issue_id).first()
            else:
                row.open_count = int(row.open_count or 0) + 1
                self.db.commit()
        elif event in {
            "update_seen",
            "follow",
            "unfollow",
            "vote",
            "comment",
            "my_issue_open",
            "push_opened",
            *share_events,
        }:
            if user_id:
                _append_user_event(
                    self.db,
                    user_id=user_id,
                    signal_id=issue_id,
                    event=event,
                    # For push_opened, share_id carries notification_id (UUID).
                    share_id=share_id,
                    ref_user_id=ref_user_id,
                    share_intent=share_intent,
                )
                self.db.commit()
        else:
            return None
        row = self.db.query(Signal).filter(Signal.id == issue_id).first()
        return {
            "ok": True,
            "impression_count": int(row.impression_count or 0) if row else 0,
            "open_count": int(row.open_count or 0) if row else 0,
        }

    def participate(
        self, issue_id: str, *, user_id: str, option_id: str
    ) -> dict | None:
        signal = (
            self.db.query(Signal)
            .options(joinedload(Signal.participation_options))
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not signal or not signal.participation_suitable:
            return None
        option = (
            self.db.query(ParticipationOption)
            .filter(
                ParticipationOption.id == option_id,
                ParticipationOption.signal_id == issue_id,
            )
            .first()
        )
        if not option:
            raise ValueError("invalid_option")

        existing = (
            self.db.query(Participation)
            .filter(
                Participation.signal_id == issue_id,
                Participation.user_id == user_id,
            )
            .first()
        )
        if existing:
            # Take a side: first take is locked. Repeat taps are idempotent.
            out = _to_issue_out(self.db, signal, user_id=user_id)
            return {
                "issue_id": issue_id,
                "my_option_id": existing.option_id,
                "participation_count": out.participation_count,
                "options": out.options,
                "is_following": out.is_following,
            }

        self.db.add(
            Participation(
                signal_id=issue_id,
                user_id=user_id,
                option_id=option_id,
            )
        )
        _append_user_event(self.db, user_id=user_id, signal_id=issue_id, event="vote")
        from app.pipeline.trend_status import apply_trend_status

        apply_trend_status(self.db, signal)
        self.db.commit()
        out = _to_issue_out(self.db, signal, user_id=user_id)
        return {
            "issue_id": issue_id,
            "my_option_id": option_id,
            "participation_count": out.participation_count,
            "options": out.options,
            "is_following": out.is_following,
        }

    def list_comments(
        self, issue_id: str, *, user_id: str | None = None, limit: int = 50
    ) -> list[IssueCommentOut]:
        limit = max(1, min(limit, 100))
        from app.services.safety_service import blocked_user_ids, hidden_target_ids

        blocked = blocked_user_ids(self.db, user_id)
        hidden = hidden_target_ids(self.db, user_id, target_type="comment")
        query = (
            self.db.query(IssueComment)
            .filter(
                IssueComment.signal_id == issue_id,
                IssueComment.status == "visible",
            )
        )
        if blocked:
            query = query.filter(~IssueComment.user_id.in_(blocked))
        if hidden:
            query = query.filter(~IssueComment.id.in_(hidden))
        rows = query.order_by(IssueComment.created_at.desc()).limit(limit).all()
        names = _user_display_names(self.db, [r.user_id for r in rows])
        return [
            _comment_out(r, display_name=names.get(r.user_id))
            for r in rows
        ]

    def add_comment(
        self, issue_id: str, *, user_id: str, content: str
    ) -> IssueCommentOut | None:
        from app.db.models import User
        from app.services.content_moderation import (
            ObjectionableContent,
            reject_objectionable,
        )

        signal = (
            self.db.query(Signal)
            .filter(Signal.id == issue_id, Signal.status == "published")
            .first()
        )
        if not signal:
            return None
        text = (content or "").strip()
        if not text:
            raise ValueError("empty_content")
        author = self.db.query(User).filter(User.id == user_id).first()
        if author is not None and (author.status or "").lower() != "active":
            raise ValueError("user_inactive")
        try:
            reject_objectionable(text)
        except ObjectionableContent as exc:
            raise ValueError(str(exc)) from exc
        row = IssueComment(
            signal_id=issue_id,
            user_id=user_id,
            content=text[:2000],
            status="visible",
        )
        self.db.add(row)
        _append_user_event(
            self.db, user_id=user_id, signal_id=issue_id, event="comment"
        )
        self.db.commit()
        self.db.refresh(row)
        names = _user_display_names(self.db, [user_id])
        return _comment_out(row, display_name=names.get(user_id))

    def my_activity(self, user_id: str, *, limit: int = 20) -> MyActivityOut:
        limit = max(1, min(limit, 50))
        votes = (
            self.db.query(Participation)
            .filter(Participation.user_id == user_id)
            .order_by(Participation.updated_at.desc())
            .limit(limit)
            .all()
        )
        follows = (
            self.db.query(IssueFollow)
            .filter(IssueFollow.user_id == user_id)
            .order_by(IssueFollow.created_at.desc())
            .limit(limit)
            .all()
        )
        vote_ids = [v.signal_id for v in votes]
        follow_ids = [f.signal_id for f in follows]
        all_ids = list(dict.fromkeys(vote_ids + follow_ids))
        signals = (
            {
                s.id: s
                for s in self.db.query(Signal)
                .options(joinedload(Signal.participation_options))
                .filter(Signal.id.in_(all_ids), Signal.status == "published")
                .all()
            }
            if all_ids
            else {}
        )
        retention = _load_retention_maps(self.db, user_id, all_ids)
        opt_counts = _bulk_option_counts(self.db, all_ids)
        comment_counts = _bulk_comment_counts(self.db, all_ids)

        def _map(sid: str) -> IssueOut | None:
            signal = signals.get(sid)
            if not signal:
                return None
            return _to_issue_out(
                self.db,
                signal,
                user_id=user_id,
                retention=retention.get(sid),
                option_counts=opt_counts.get(sid, {}),
                comment_count=comment_counts.get(sid, 0),
            )

        participations = [x for sid in vote_ids if (x := _map(sid))]
        followed = [x for sid in follow_ids if (x := _map(sid))]

        comments = (
            self.db.query(IssueComment)
            .filter(
                IssueComment.user_id == user_id,
                IssueComment.status == "visible",
            )
            .order_by(IssueComment.created_at.desc())
            .limit(limit)
            .all()
        )
        names = _user_display_names(self.db, [user_id])
        my_name = names.get(user_id)
        comment_issue_ids = list(dict.fromkeys(c.signal_id for c in comments))
        comment_titles = (
            {
                s.id: (s.title or "")
                for s in self.db.query(Signal)
                .filter(Signal.id.in_(comment_issue_ids))
                .all()
            }
            if comment_issue_ids
            else {}
        )
        comment_outs = [
            _comment_out(
                c,
                display_name=my_name,
                issue_title=comment_titles.get(c.signal_id, ""),
            )
            for c in comments
        ]
        from app.services.take_service import build_contributor_activity

        stats, deep = build_contributor_activity(self.db, user_id, limit=limit)
        return MyActivityOut(
            participations=participations,
            followed=followed,
            comments=comment_outs,
            contributor_stats=stats,
            my_deep_thoughts=deep,
        )


def replace_participation_options(
    db: Session, signal: Signal, labels: list[str]
) -> None:
    """Replace options for a signal (used at publish time)."""
    for old in list(signal.participation_options or []):
        db.delete(old)
    db.flush()
    for i, label in enumerate(labels[:4]):
        text = (label or "").strip()
        if not text:
            continue
        db.add(
            ParticipationOption(
                signal_id=signal.id,
                label=text[:200],
                display_order=i,
            )
        )


def apply_issue_fields(
    signal: Signal,
    domain,
    *,
    min_replies_for_trending: int | None = None,
    db: Session | None = None,
) -> None:
    """Copy Issue fields from domain MarketSignal onto ORM Signal."""
    from app.core.config import get_settings
    from app.pipeline.trend_status import apply_trend_status, set_ai_trending_hint

    signal.category = getattr(domain, "category", None) or signal.category
    signal.topic = getattr(domain, "topic", None) or signal.topic
    column_body = str(getattr(domain, "column_body", "") or "").strip()
    if column_body:
        signal.column_body = column_body
    if getattr(domain, "title", None):
        signal.title = domain.title
    if getattr(domain, "summary", None):
        signal.summary = domain.summary
    if getattr(domain, "why_it_matters", None) is not None:
        signal.why_it_matters = domain.why_it_matters or signal.why_it_matters
    if getattr(domain, "key_points", None):
        signal.key_points = domain.key_points
    suitable = bool(getattr(domain, "participation_suitable", False))
    signal.participation_suitable = suitable
    signal.participation_type = (
        getattr(domain, "participation_type", None) if suitable else None
    )
    signal.participation_question = (
        getattr(domain, "participation_question", None) if suitable else None
    )
    reply_peak = int(getattr(domain, "source_reply_peak", 0) or 0)
    if reply_peak > 0:
        signal.source_reply_peak = max(int(signal.source_reply_peak or 0), reply_peak)
    else:
        reply_peak = int(signal.source_reply_peak or 0)

    settings = get_settings()
    min_replies = (
        min_replies_for_trending
        if min_replies_for_trending is not None
        else settings.issue_min_reply_count
    )
    ai_trending = bool(getattr(domain, "is_trending", False))
    set_ai_trending_hint(signal, ai_trending)

    importance = float(getattr(domain, "importance", 0) or 0)
    confidence = float(getattr(domain, "confidence", 0) or 0)
    providers = getattr(domain, "providers", None) or []
    diversity = min(0.2, 0.05 * len(set(providers)))
    participate_boost = 0.15 if suitable else 0.0

    if db is not None:
        resolution = apply_trend_status(
            db, signal, ai_trending=ai_trending, settings=settings
        )
        trending_boost = 0.2 if resolution.final_status == "TRENDING" else 0.0
    else:
        # Tests / callers without session: external AI gate only (no internal).
        external_ok = ai_trending and reply_peak >= min_replies
        signal.is_trending = False
        signal.trend_status = "NORMAL"
        trending_boost = 0.2 if external_ok else 0.0

    signal.trend_score = max(
        float(getattr(domain, "trend_score", 0) or 0),
        min(
            1.0,
            importance * 0.55
            + confidence * 0.1
            + diversity
            + participate_boost
            + trending_boost,
        ),
    )
