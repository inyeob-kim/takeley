"""Active symbol universe: shared US monitor set ∪ watchlist ∪ MVP seed."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.models import Asset, WatchlistItem
from app.db.repositories import AssetRepository
from app.services.korean_names import name_en_for, name_ko_for


@dataclass(frozen=True)
class UniverseSymbol:
    symbol: str
    name: str
    name_ko: str | None = None
    exchange: str | None = None
    market: str = "US"


def _ensure_asset(
    repo: AssetRepository,
    *,
    symbol: str,
    name: str | None = None,
    name_ko: str | None = None,
) -> Asset:
    sym = symbol.upper()
    en = name or name_en_for(sym)
    ko = name_ko or name_ko_for(sym)
    return repo.get_or_create(
        symbol=sym,
        name=en,
        kind="asset",
        name_ko=ko,
        exchange="US",
        market="US",
    )


def active_universe(db: Session) -> list[UniverseSymbol]:
    """
    Shared intelligence universe for ingest:
    1) Configured US monitor set (mega-cap / ETFs)
    2) MVP seed
    3) All watchlist symbols (personalization overlay)
    """
    settings = get_settings()
    repo = AssetRepository(db)
    by_symbol: dict[str, UniverseSymbol] = {}

    for sym in settings.monitor_symbols():
        asset = _ensure_asset(repo, symbol=sym)
        by_symbol[asset.symbol.upper()] = UniverseSymbol(
            symbol=asset.symbol.upper(),
            name=asset.name or name_en_for(asset.symbol),
            name_ko=asset.name_ko or name_ko_for(asset.symbol),
            exchange=asset.exchange or "US",
            market=(asset.market or "US"),
        )

    mvp = _ensure_asset(
        repo,
        symbol=settings.mvp_asset_symbol,
        name=settings.mvp_asset_name,
        name_ko=settings.mvp_asset_name_ko,
    )
    by_symbol[mvp.symbol.upper()] = UniverseSymbol(
        symbol=mvp.symbol.upper(),
        name=mvp.name or settings.mvp_asset_name,
        name_ko=mvp.name_ko or settings.mvp_asset_name_ko,
        exchange=mvp.exchange or "US",
        market=(mvp.market or "US"),
    )

    rows = (
        db.query(WatchlistItem)
        .options(joinedload(WatchlistItem.asset))
        .all()
    )
    for item in rows:
        asset: Asset | None = item.asset
        if not asset:
            continue
        sym = asset.symbol.upper()
        if not asset.name_ko:
            ko = name_ko_for(sym)
            if ko:
                asset.name_ko = ko
                db.commit()
        by_symbol[sym] = UniverseSymbol(
            symbol=sym,
            name=asset.name or sym,
            name_ko=asset.name_ko or name_ko_for(sym),
            exchange=asset.exchange or "US",
            market=(asset.market or "US"),
        )

    return sorted(by_symbol.values(), key=lambda u: u.symbol)


def search_query_for(entry: UniverseSymbol) -> str:
    return f"{entry.name} OR {entry.symbol}"


def x_search_universe(
    universe: list[UniverseSymbol],
    *,
    budget: int | None = None,
    cursor_repo=None,
) -> list[UniverseSymbol]:
    """Cap X symbol-search fan-out; rotate through monitor-first order across cycles."""
    settings = get_settings()
    limit = budget if budget is not None else settings.x_search_query_budget
    if limit <= 0:
        return []

    by_symbol = {u.symbol.upper(): u for u in universe}
    preferred: list[UniverseSymbol] = []
    seen: set[str] = set()
    for sym in settings.monitor_symbols():
        entry = by_symbol.get(sym.upper())
        if entry and entry.symbol not in seen:
            preferred.append(entry)
            seen.add(entry.symbol)
    rest = [u for u in universe if u.symbol not in seen]
    ordered = preferred + rest
    if not ordered:
        return []

    offset = 0
    if cursor_repo is not None:
        raw = cursor_repo.get("x", "search:rotate_offset")
        if raw and str(raw).isdigit():
            offset = int(raw) % len(ordered)

    rotated = ordered[offset:] + ordered[:offset]
    selected = rotated[:limit]

    if cursor_repo is not None and ordered:
        next_offset = (offset + len(selected)) % len(ordered)
        cursor_repo.set("x", "search:rotate_offset", str(next_offset))

    return selected
