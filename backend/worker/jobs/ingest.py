"""Ingest job: pull from SourceProviders into raw_items (no LLM)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import log_raw_items
from app.core.usage import (
    RSS_REQUESTS,
    KR_RSS_REQUESTS,
    DART_REQUESTS,
    X_API_REQUESTS,
    X_POSTS_RECEIVED,
    X_SEARCH_REQUESTS,
    record_usage,
)
from app.db.repositories import AssetRepository, CursorRepository, RawItemRepository
from app.pipeline.markets import (
    is_kr_equity_symbol,
    search_query_for_kr,
    split_universe,
)
from app.pipeline.industries import (
    INDUSTRY_LABELS,
    build_topic_lanes,
    legacy_topic_since_cursor_key,
    select_topic_lanes,
    topic_since_cursor_key,
)
from app.pipeline.issue_heat import pick_hottest
from app.pipeline.normalize import (
    is_keep_for_intelligence,
    is_relevant_to_symbol,
)
from app.providers.korean_news_provider import KoreanNewsProvider
from app.providers.news_provider import NewsProvider
from app.providers.official_provider import OfficialProvider
from app.providers.reddit_provider import RedditProvider
from app.providers.x_provider import XProvider
from app.services.korean_names import name_ko_for
from app.services.universe import (
    UniverseSymbol,
    active_universe,
    search_query_for,
    x_search_universe,
)

logger = logging.getLogger(__name__)


def _names_by_symbol(universe: list[UniverseSymbol]) -> dict[str, str]:
    return {u.symbol: u.name for u in universe}


def _ingest_due(
    cursor_repo: CursorRepository,
    *,
    provider: str,
    cursor_key: str,
    interval_seconds: int,
    force: bool = False,
) -> bool:
    if force:
        return True
    last = cursor_repo.get(provider, cursor_key)
    if not last:
        return True
    try:
        last_at = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    age = (datetime.now(timezone.utc) - last_at).total_seconds()
    due = age >= interval_seconds
    logger.debug(
        "ingest_due provider=%s key=%s age_s=%.0f interval_s=%s due=%s",
        provider,
        cursor_key,
        age,
        interval_seconds,
        due,
    )
    return due


def _mark_ingest_fetch(
    cursor_repo: CursorRepository, *, provider: str, cursor_key: str
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor_repo.set(provider, cursor_key, now)


def _ingest_x_accounts(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    universe: list[UniverseSymbol],
    *,
    force: bool = False,
) -> tuple[int, int]:
    """Configured account timelines (quality boost). Symbol search is separate."""
    settings = get_settings()
    accounts = settings.tracked_x_accounts()
    if not accounts:
        logger.info("ingest provider=x mode=accounts skipped reason=no_accounts")
        return 0, 0

    if not _ingest_due(
        cursor_repo,
        provider="x",
        cursor_key="accounts:last_fetch_at",
        interval_seconds=settings.x_accounts_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=x mode=accounts skipped reason=not_due")
        return 0, 0

    provider = XProvider(accounts=accounts)
    fetched = 0
    inserted = 0
    names = _names_by_symbol(universe)
    symbols = [u.symbol for u in universe]
    macro_keys = settings.macro_keywords()

    if not provider.bearer_token:
        items = provider.fetch(limit=20)
        relevant = [
            i
            for i in items
            if is_keep_for_intelligence(
                i.text, symbols, names, macro_keywords=macro_keys
            )
            or (i.raw_payload or {}).get("demo")
        ]
        inserted += raw_repo.upsert_many(relevant)
        fetched += len(items)
        log_raw_items(logger, items, context="x.demo")
        record_usage(
            X_POSTS_RECEIVED,
            len(items),
            tags={"mode": "demo"},
            scope_type="shared",
        )
        _mark_ingest_fetch(
            cursor_repo, provider="x", cursor_key="accounts:last_fetch_at"
        )
        logger.info(
            "ingest provider=x mode=demo fetched=%s inserted=%s",
            len(items),
            inserted,
        )
        return fetched, inserted

    for username in accounts:
        cursor_key = f"account:{username}:since_id"
        since_id = cursor_repo.get("x", cursor_key)
        cached_uid = cursor_repo.get("x", f"user_id:{username.lower()}")
        used_cache = bool(cached_uid and str(cached_uid).isdigit())

        # get_user when cache miss
        if not used_cache:
            record_usage(
                X_API_REQUESTS,
                1,
                tags={"endpoint": "get_user", "account": username},
                scope_type="shared",
            )
        resolved = provider.resolve_user_id(username, cached_user_id=cached_uid)
        if resolved and resolved != cached_uid:
            cursor_repo.set("x", f"user_id:{username.lower()}", resolved)

        items = provider.fetch_account(
            username=username,
            since_id=since_id,
            limit=10,
            cached_user_id=resolved,
        )
        record_usage(
            X_API_REQUESTS,
            1,
            tags={"endpoint": "get_users_tweets", "account": username},
            scope_type="shared",
        )
        record_usage(
            X_POSTS_RECEIVED,
            len(items),
            tags={"mode": "account", "account": username},
            scope_type="shared",
        )

        relevant = [
            i
            for i in items
            if is_keep_for_intelligence(
                i.text, symbols, names, macro_keywords=macro_keys
            )
        ]
        n = raw_repo.upsert_many(relevant)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, items, context=f"x.account@{username}")

        if items:
            newest = max(
                items,
                key=lambda x: int(x.external_id) if x.external_id.isdigit() else 0,
            )
            if newest.external_id.isdigit():
                cursor_repo.set("x", cursor_key, newest.external_id)

        logger.info(
            "ingest provider=x account=%s fetched=%s inserted=%s since_id=%s cache=%s",
            username,
            len(items),
            n,
            since_id,
            used_cache,
        )

    _mark_ingest_fetch(cursor_repo, provider="x", cursor_key="accounts:last_fetch_at")
    logger.info(
        "ingest provider=x mode=accounts accounts=%s fetched=%s inserted=%s",
        len(accounts),
        fetched,
        inserted,
    )
    return fetched, inserted


def _ingest_x_search(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    universe: list[UniverseSymbol],
    *,
    force: bool = False,
) -> tuple[int, int]:
    settings = get_settings()
    if not _ingest_due(
        cursor_repo,
        provider="x",
        cursor_key="search:last_fetch_at",
        interval_seconds=settings.x_search_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=x_search skipped reason=not_due")
        return 0, 0

    provider = XProvider()
    fetched = 0
    inserted = 0

    if not provider.bearer_token:
        logger.info("ingest provider=x_search skipped reason=no_bearer")
        return 0, 0

    search_universe = x_search_universe(
        universe, budget=settings.x_search_query_budget, cursor_repo=cursor_repo
    )
    logger.info(
        "ingest provider=x_search budget=%s symbols=%s",
        len(search_universe),
        ",".join(u.symbol for u in search_universe) or "(none)",
    )

    for entry in search_universe:
        if is_kr_equity_symbol(entry.symbol):
            continue
        query = f"({search_query_for(entry)}) -is:retweet"
        cursor_key = f"search:{entry.symbol}:since_id"
        since_id = cursor_repo.get("x", cursor_key)
        try:
            items = provider.fetch_search(
                query=query,
                since_id=since_id,
                limit=10,
            )
        except Exception:
            logger.exception(
                "ingest provider=x_search symbol=%s failed; continuing", entry.symbol
            )
            continue

        record_usage(
            X_SEARCH_REQUESTS,
            1,
            tags={"symbol": entry.symbol},
            scope_type="shared",
            symbol=entry.symbol,
        )
        record_usage(
            X_API_REQUESTS,
            1,
            tags={"endpoint": "search_recent_tweets", "symbol": entry.symbol},
            scope_type="shared",
            symbol=entry.symbol,
        )
        record_usage(
            X_POSTS_RECEIVED,
            len(items),
            tags={"mode": "search", "symbol": entry.symbol},
            scope_type="shared",
            symbol=entry.symbol,
        )

        relevant = [
            i
            for i in items
            if is_relevant_to_symbol(i.text, entry.symbol, entry.name)
        ]
        n = raw_repo.upsert_many(relevant)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, items, context=f"x.search:{entry.symbol}")

        if items:
            numeric = [i for i in items if i.external_id.isdigit()]
            if numeric:
                newest = max(numeric, key=lambda x: int(x.external_id))
                cursor_repo.set("x", cursor_key, newest.external_id)

        logger.info(
            "ingest provider=x_search symbol=%s fetched=%s inserted=%s query=%s",
            entry.symbol,
            len(items),
            n,
            query[:120],
        )

    _mark_ingest_fetch(cursor_repo, provider="x", cursor_key="search:last_fetch_at")
    logger.info(
        "ingest provider=x_search symbols=%s fetched=%s inserted=%s",
        len(universe),
        fetched,
        inserted,
    )
    return fetched, inserted


def _resolve_topic_since_id(
    cursor_repo: CursorRepository,
    *,
    industry_key: str,
    source_lane: str,
) -> str | None:
    """Lane since_id with safe seed from pre-lane industry cursor (never delete old)."""
    lane_key = topic_since_cursor_key(industry_key, source_lane)
    existing = cursor_repo.get("x", lane_key)
    if existing:
        return existing
    legacy = cursor_repo.get("x", legacy_topic_since_cursor_key(industry_key))
    if legacy:
        cursor_repo.set("x", lane_key, legacy)
        return legacy
    return None


def _ingest_x_topics(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    *,
    force: bool = False,
) -> tuple[int, int]:
    """Industry × korea/global discovery lanes (budget-capped round-robin)."""
    settings = get_settings()
    if not settings.issue_x_topic_enabled:
        logger.info("ingest provider=x_topic skipped reason=disabled")
        return 0, 0

    if not _ingest_due(
        cursor_repo,
        provider="x",
        cursor_key="topic:last_fetch_at",
        interval_seconds=settings.x_topic_search_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=x_topic skipped reason=not_due")
        return 0, 0

    provider = XProvider()
    if not provider.bearer_token:
        logger.info("ingest provider=x_topic skipped reason=no_bearer")
        return 0, 0

    lanes = build_topic_lanes(settings.issue_industry_keys())
    if not lanes:
        logger.info("ingest provider=x_topic skipped reason=no_industries")
        return 0, 0

    budget = max(1, min(settings.x_topic_query_budget, len(lanes)))
    offset = 0
    raw_off = cursor_repo.get("x", "topic:rotate_offset")
    if raw_off and str(raw_off).isdigit():
        offset = int(raw_off) % len(lanes)
    selected, next_offset = select_topic_lanes(lanes, budget=budget, offset=offset)
    cursor_repo.set("x", "topic:rotate_offset", str(next_offset))

    fetched = 0
    inserted = 0
    logger.info(
        "ingest provider=x_topic budget=%s lanes=%s",
        budget,
        ",".join(f"{lane.industry_key}/{lane.source_lane}" for lane in selected),
    )

    for lane in selected:
        industry_key = lane.industry_key
        source_lane = lane.source_lane
        query = lane.query
        cursor_key = topic_since_cursor_key(industry_key, source_lane)
        since_id = _resolve_topic_since_id(
            cursor_repo,
            industry_key=industry_key,
            source_lane=source_lane,
        )
        try:
            items = provider.fetch_search(
                query=query,
                since_id=since_id,
                limit=15,
            )
        except Exception:
            logger.exception(
                "ingest provider=x_topic industry=%s lane=%s failed; continuing",
                industry_key,
                source_lane,
            )
            continue

        label = INDUSTRY_LABELS.get(industry_key, industry_key)
        for item in items:
            payload = dict(item.raw_payload or {})
            payload["issue_industry"] = industry_key
            payload["issue_category"] = label
            payload["source_lane"] = source_lane
            payload["search_query"] = query
            item.raw_payload = payload

        # Heat ranks/caps pool size only — never hard-rejects Issue creation.
        hot = pick_hottest(
            items,
            limit=settings.issue_topic_keep_per_query,
            min_score=settings.issue_min_engagement_score,
            min_replies=settings.issue_min_reply_count,
        )
        if len(items) > settings.issue_topic_keep_per_query:
            hot_ids = {i.external_id for i in hot}
            fillers = [i for i in items if i.external_id not in hot_ids]
            need = max(0, settings.issue_topic_keep_per_query - len(hot))
            hot = list(hot) + fillers[:need]
        else:
            hot = list(items)
        cold_dropped = len(items) - len(hot)
        if cold_dropped:
            logger.info(
                "ingest provider=x_topic industry=%s lane=%s heat_drop=%s kept=%s",
                industry_key,
                source_lane,
                cold_dropped,
                len(hot),
            )

        record_usage(
            X_SEARCH_REQUESTS,
            1,
            tags={
                "industry": industry_key,
                "source_lane": source_lane,
                "mode": "topic",
            },
            scope_type="shared",
        )
        record_usage(
            X_API_REQUESTS,
            1,
            tags={
                "endpoint": "search_recent_tweets",
                "industry": industry_key,
                "source_lane": source_lane,
            },
            scope_type="shared",
        )
        record_usage(
            X_POSTS_RECEIVED,
            len(items),
            tags={
                "mode": "topic",
                "industry": industry_key,
                "source_lane": source_lane,
            },
            scope_type="shared",
        )

        n = raw_repo.upsert_many(hot)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, hot, context=f"x.topic:{industry_key}:{source_lane}")

        if items:
            numeric = [i for i in items if i.external_id.isdigit()]
            if numeric:
                newest = max(numeric, key=lambda x: int(x.external_id))
                cursor_repo.set("x", cursor_key, newest.external_id)

        logger.info(
            "ingest provider=x_topic industry=%s lane=%s fetched=%s hot=%s inserted=%s query=%s",
            industry_key,
            source_lane,
            len(items),
            len(hot),
            n,
            query[:120],
        )

    _mark_ingest_fetch(cursor_repo, provider="x", cursor_key="topic:last_fetch_at")
    logger.info(
        "ingest provider=x_topic lanes=%s fetched=%s inserted=%s",
        len(selected),
        fetched,
        inserted,
    )
    return fetched, inserted


def _ingest_x_dynamic(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    *,
    force: bool = False,
) -> tuple[int, int]:
    """Extra X searches from remembered Understanding topics (not Issue hard gates)."""
    settings = get_settings()
    if not settings.issue_dynamic_query_enabled:
        return 0, 0
    if not _ingest_due(
        cursor_repo,
        provider="x",
        cursor_key="dynamic:last_fetch_at",
        interval_seconds=settings.x_topic_search_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=x_dynamic skipped reason=not_due")
        return 0, 0

    from app.pipeline.dynamic_query import dynamic_search_queries

    queries = dynamic_search_queries(
        cursor_repo, budget=settings.issue_dynamic_query_budget
    )
    if not queries:
        logger.info("ingest provider=x_dynamic skipped reason=no_topics")
        return 0, 0

    provider = XProvider()
    if not provider.bearer_token:
        return 0, 0

    fetched = 0
    inserted = 0
    for qi, query in enumerate(queries):
        try:
            items = provider.fetch_search(query=query, limit=10)
        except Exception:
            logger.exception("ingest provider=x_dynamic query failed")
            continue
        for item in items:
            payload = dict(item.raw_payload or {})
            payload["issue_industry"] = "dynamic"
            payload["issue_category"] = "Tech"
            payload["search_query"] = query
            payload["ingest_mode"] = "dynamic"
            item.raw_payload = payload
        keep = pick_hottest(
            items,
            limit=settings.issue_topic_keep_per_query,
            min_score=0.0,
            min_replies=0,
        )
        # Always keep up to budget even if cold — LLM decides later
        if len(items) > settings.issue_topic_keep_per_query:
            keep_ids = {i.external_id for i in keep}
            fillers = [i for i in items if i.external_id not in keep_ids]
            need = max(0, settings.issue_topic_keep_per_query - len(keep))
            keep = list(keep) + fillers[:need]
        else:
            keep = list(items)
        record_usage(
            X_SEARCH_REQUESTS,
            1,
            tags={"mode": "dynamic", "qi": str(qi)},
            scope_type="shared",
        )
        n = raw_repo.upsert_many(keep)
        fetched += len(items)
        inserted += n
        logger.info(
            "ingest provider=x_dynamic qi=%s fetched=%s kept=%s inserted=%s query=%s",
            qi,
            len(items),
            len(keep),
            n,
            query[:120],
        )
    _mark_ingest_fetch(cursor_repo, provider="x", cursor_key="dynamic:last_fetch_at")
    logger.info(
        "ingest provider=x_dynamic queries=%s fetched=%s inserted=%s",
        len(queries),
        fetched,
        inserted,
    )
    return fetched, inserted


def _ingest_news(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    universe: list[UniverseSymbol],
    *,
    force: bool = False,
) -> tuple[int, int]:
    """EN Google News RSS for US (non-KR) symbols only."""
    settings = get_settings()
    us_universe = [e for e in universe if not is_kr_equity_symbol(e.symbol)]
    if not us_universe:
        logger.info("ingest provider=news skipped reason=no_us_symbols")
        return 0, 0

    if not _ingest_due(
        cursor_repo,
        provider="news",
        cursor_key="rss:last_fetch_at",
        interval_seconds=settings.rss_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=news skipped reason=not_due")
        return 0, 0

    provider = NewsProvider()
    fetched = 0
    inserted = 0

    for entry in us_universe:
        query = search_query_for(entry)
        cursor_key = f"rss:{entry.symbol}:since_id"
        since_id = cursor_repo.get("news", cursor_key)
        items = provider.fetch(
            query=query,
            since_id=since_id,
            limit=20,
            symbol=entry.symbol,
            name=entry.name,
        )
        record_usage(
            RSS_REQUESTS,
            1,
            tags={"symbol": entry.symbol, "locale": "en"},
            scope_type="shared",
            symbol=entry.symbol,
        )
        n = raw_repo.upsert_many(items)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, items, context=f"news.rss:{entry.symbol}")
        if items:
            newest = max(items, key=lambda x: x.external_id)
            cursor_repo.set("news", cursor_key, newest.external_id)
        logger.debug(
            "ingest provider=news symbol=%s fetched=%s inserted=%s",
            entry.symbol,
            len(items),
            n,
        )

    _mark_ingest_fetch(cursor_repo, provider="news", cursor_key="rss:last_fetch_at")
    logger.info(
        "ingest provider=news symbols=%s fetched=%s inserted=%s",
        len(us_universe),
        fetched,
        inserted,
    )
    return fetched, inserted


def _ingest_kr_news(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    universe: list[UniverseSymbol],
    *,
    force: bool = False,
) -> tuple[int, int]:
    settings = get_settings()
    if not settings.kr_news_enabled:
        logger.info("ingest provider=kr_news skipped reason=disabled")
        return 0, 0

    kr_universe = [e for e in universe if is_kr_equity_symbol(e.symbol)]
    if not kr_universe:
        logger.info("ingest provider=kr_news skipped reason=no_kr_symbols")
        return 0, 0

    if not _ingest_due(
        cursor_repo,
        provider="news",
        cursor_key="kr_rss:last_fetch_at",
        interval_seconds=settings.kr_news_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=kr_news skipped reason=not_due")
        return 0, 0

    provider = KoreanNewsProvider()
    fetched = 0
    inserted = 0

    for entry in kr_universe:
        query = search_query_for_kr(entry)
        cursor_key = f"kr_rss:{entry.symbol}:since_id"
        since_id = cursor_repo.get("news", cursor_key)
        items = provider.fetch(
            query=query,
            since_id=since_id,
            limit=20,
            symbol=entry.symbol,
            name=entry.name,
        )
        record_usage(
            KR_RSS_REQUESTS,
            1,
            tags={"symbol": entry.symbol, "locale": "ko"},
            scope_type="shared",
            symbol=entry.symbol,
        )
        n = raw_repo.upsert_many(items)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, items, context=f"news.kr:{entry.symbol}")
        if items:
            newest = max(items, key=lambda x: x.external_id)
            cursor_repo.set("news", cursor_key, newest.external_id)
        logger.debug(
            "ingest provider=kr_news symbol=%s fetched=%s inserted=%s",
            entry.symbol,
            len(items),
            n,
        )

    _mark_ingest_fetch(cursor_repo, provider="news", cursor_key="kr_rss:last_fetch_at")
    logger.info(
        "ingest provider=kr_news symbols=%s fetched=%s inserted=%s",
        len(kr_universe),
        fetched,
        inserted,
    )
    return fetched, inserted


def _ingest_dart(
    raw_repo: RawItemRepository,
    cursor_repo: CursorRepository,
    universe: list[UniverseSymbol],
    *,
    force: bool = False,
) -> tuple[int, int]:
    settings = get_settings()
    kr_universe = [e for e in universe if is_kr_equity_symbol(e.symbol)]
    if not kr_universe:
        logger.info("ingest provider=dart skipped reason=no_kr_symbols")
        return 0, 0

    if not settings.dart_api_key.strip():
        logger.info("ingest provider=dart skipped reason=no_api_key")
        return 0, 0

    if not _ingest_due(
        cursor_repo,
        provider="official",
        cursor_key="dart:last_fetch_at",
        interval_seconds=settings.dart_interval_seconds,
        force=force,
    ):
        logger.info("ingest provider=dart skipped reason=not_due")
        return 0, 0

    provider = OfficialProvider()
    fetched = 0
    inserted = 0

    for entry in kr_universe:
        cursor_key = f"dart:{entry.symbol}:since_id"
        since_id = cursor_repo.get("official", cursor_key)
        items = provider.fetch(
            since_id=since_id,
            limit=20,
            symbol=entry.symbol,
            name=entry.name,
        )
        record_usage(
            DART_REQUESTS,
            1,
            tags={"symbol": entry.symbol},
            scope_type="shared",
            symbol=entry.symbol,
        )
        n = raw_repo.upsert_many(items)
        fetched += len(items)
        inserted += n
        log_raw_items(logger, items, context=f"dart:{entry.symbol}")
        if items:
            # rcept_no is monotonic-ish string; store newest external_id
            newest = max(items, key=lambda x: x.external_id)
            cursor_repo.set("official", cursor_key, newest.external_id.replace("dart:", ""))
        logger.debug(
            "ingest provider=dart symbol=%s fetched=%s inserted=%s",
            entry.symbol,
            len(items),
            n,
        )

    _mark_ingest_fetch(cursor_repo, provider="official", cursor_key="dart:last_fetch_at")
    logger.info(
        "ingest provider=dart symbols=%s fetched=%s inserted=%s",
        len(kr_universe),
        fetched,
        inserted,
    )
    return fetched, inserted


def run_ingest(db: Session) -> dict:
    settings = get_settings()
    AssetRepository(db).get_or_create(
        symbol=settings.mvp_asset_symbol,
        name=settings.mvp_asset_name,
        kind="asset",
        name_ko=settings.mvp_asset_name_ko,
        exchange="US",
        market="US",
    )

    universe = active_universe(db)
    us_universe, kr_universe = split_universe(universe)
    logger.info(
        "ingest start universe=%s us=%s kr=%s",
        ",".join(u.symbol for u in universe) or "(empty)",
        ",".join(u.symbol for u in us_universe) or "(none)",
        ",".join(u.symbol for u in kr_universe) or "(none)",
    )

    raw_repo = RawItemRepository(db)
    cursor_repo = CursorRepository(db)

    total_fetched = 0
    total_inserted = 0

    # US path: X + EN Google News
    f, i = _ingest_x_accounts(raw_repo, cursor_repo, universe)
    total_fetched += f
    total_inserted += i

    if not settings.issue_ingest_focus:
        f, i = _ingest_x_search(raw_repo, cursor_repo, us_universe)
        total_fetched += f
        total_inserted += i
    else:
        logger.info("ingest provider=x_search skipped reason=issue_ingest_focus")

    f, i = _ingest_x_topics(raw_repo, cursor_repo)
    total_fetched += f
    total_inserted += i

    f, i = _ingest_x_dynamic(raw_repo, cursor_repo)
    total_fetched += f
    total_inserted += i

    # Full-body Google News enrich is slow (per-article HTTP) and blocks Issue process.
    if not settings.issue_ingest_focus:
        f, i = _ingest_news(raw_repo, cursor_repo, us_universe)
        total_fetched += f
        total_inserted += i
    else:
        logger.info("ingest provider=news skipped reason=issue_ingest_focus")

    # KR path: OpenDART + Korean Google News
    if not settings.issue_ingest_focus:
        f, i = _ingest_dart(raw_repo, cursor_repo, kr_universe)
        total_fetched += f
        total_inserted += i

        f, i = _ingest_kr_news(raw_repo, cursor_repo, kr_universe)
        total_fetched += f
        total_inserted += i
    else:
        logger.info("ingest provider=dart/kr_news skipped reason=issue_ingest_focus")

    if not settings.issue_ingest_focus:
        for provider in (RedditProvider(),):
            items = provider.fetch(limit=5)
            n = raw_repo.upsert_many(items)
            total_fetched += len(items)
            total_inserted += n
            log_raw_items(logger, items, context=f"{provider.name.value}")
            logger.info(
                "ingest provider=%s fetched=%s inserted=%s",
                provider.name.value,
                len(items),
                n,
            )
    else:
        logger.info("ingest provider=reddit skipped reason=issue_ingest_focus")

    return {
        "fetched": total_fetched,
        "inserted": total_inserted,
        "universe": [u.symbol for u in universe],
        "universe_us": [u.symbol for u in us_universe],
        "universe_kr": [u.symbol for u in kr_universe],
        "issue_ingest_focus": settings.issue_ingest_focus,
    }


def run_ingest_symbol(db: Session, *, symbol: str, name: str | None = None) -> dict:
    """On-demand ingest for one symbol. Routes US vs KR providers."""
    raw = (symbol or "").strip()
    sym = raw.zfill(6) if raw.isdigit() else raw.upper()
    label = (name or sym).strip() or sym
    is_kr = is_kr_equity_symbol(sym)
    AssetRepository(db).get_or_create(
        symbol=sym,
        name=label,
        kind="asset",
        name_ko=None if is_kr else name_ko_for(sym),
        exchange=None if is_kr else "US",
        market="KR" if is_kr else "US",
    )
    entry = UniverseSymbol(symbol=sym, name=label)
    universe = [entry]

    raw_repo = RawItemRepository(db)
    cursor_repo = CursorRepository(db)

    total_fetched = 0
    total_inserted = 0

    logger.info(
        "ingest_on_demand start symbol=%s market=%s",
        sym,
        "KR" if is_kr_equity_symbol(sym) else "US",
    )

    if is_kr_equity_symbol(sym):
        f, i = _ingest_dart(raw_repo, cursor_repo, universe, force=True)
        total_fetched += f
        total_inserted += i
        f, i = _ingest_kr_news(raw_repo, cursor_repo, universe, force=True)
        total_fetched += f
        total_inserted += i
    else:
        f, i = _ingest_x_search(raw_repo, cursor_repo, universe, force=True)
        total_fetched += f
        total_inserted += i
        f, i = _ingest_news(raw_repo, cursor_repo, universe, force=True)
        total_fetched += f
        total_inserted += i

    logger.info(
        "ingest_on_demand done symbol=%s fetched=%s inserted=%s",
        sym,
        total_fetched,
        total_inserted,
    )
    return {
        "fetched": total_fetched,
        "inserted": total_inserted,
        "universe": [sym],
        "mode": "on_demand",
        "market": "KR" if is_kr_equity_symbol(sym) else "US",
    }
