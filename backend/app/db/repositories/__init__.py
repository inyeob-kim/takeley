from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    Asset,
    Event,
    EventRawItem,
    IngestCursor,
    MacroEvent,
    RawItem,
    Signal,
    SubscriptionPayment,
    User,
    WatchlistItem,
)
from app.domain.models import MacroCalendarItem
from app.domain.models import RawItem as RawItemDomain
from app.pipeline.normalize import content_fingerprint, normalize_text


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(
        self,
        symbol: str,
        name: str,
        kind: str = "asset",
        *,
        name_ko: str | None = None,
        exchange: str | None = None,
        market: str | None = "US",
    ) -> Asset:
        symbol = symbol.upper()
        asset = self.db.query(Asset).filter(Asset.symbol == symbol).one_or_none()
        if asset:
            changed = False
            # Refresh display name if we only stored the ticker earlier.
            if name and asset.name == asset.symbol and name != asset.symbol:
                asset.name = name
                changed = True
            if name_ko and not (asset.name_ko or "").strip():
                asset.name_ko = name_ko
                changed = True
            if exchange and not (asset.exchange or "").strip():
                asset.exchange = exchange
                changed = True
            if market and not (asset.market or "").strip():
                asset.market = market
                changed = True
            if changed:
                self.db.commit()
                self.db.refresh(asset)
            return asset
        asset = Asset(
            symbol=symbol,
            name=name,
            kind=kind,
            name_ko=name_ko,
            exchange=exchange,
            market=market,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_by_symbol(self, symbol: str) -> Optional[Asset]:
        return (
            self.db.query(Asset)
            .filter(Asset.symbol == symbol.upper())
            .one_or_none()
        )

    def search(self, query: str, *, limit: int = 20) -> list[Asset]:
        q = query.strip()
        if not q:
            return []
        pattern = f"%{q}%"
        return (
            self.db.query(Asset)
            .filter(
                or_(
                    Asset.symbol.ilike(pattern),
                    Asset.name.ilike(pattern),
                    Asset.name_ko.ilike(pattern),
                )
            )
            .order_by(Asset.symbol.asc())
            .limit(limit)
            .all()
        )

    def labels_for_symbols(self, symbols: list[str]) -> dict[str, str]:
        """symbol → display label (Korean preferred)."""
        from app.services.korean_names import display_label, name_ko_for

        cleaned = [s.upper() for s in symbols if s]
        if not cleaned:
            return {}
        rows = self.db.query(Asset).filter(Asset.symbol.in_(cleaned)).all()
        by_sym = {r.symbol.upper(): r for r in rows}
        out: dict[str, str] = {}
        for sym in cleaned:
            row = by_sym.get(sym)
            if row:
                out[sym] = display_label(
                    sym, name_ko=row.name_ko, name=row.name
                )
            else:
                out[sym] = display_label(sym, name_ko=name_ko_for(sym))
        return out


class RawItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_many(self, items: list[RawItemDomain]) -> int:
        inserted = 0
        for item in items:
            exists = (
                self.db.query(RawItem)
                .filter(
                    RawItem.provider == item.provider.value,
                    RawItem.external_id == item.external_id,
                )
                .one_or_none()
            )
            if exists:
                continue

            # Cross-source near-dup skip by fingerprint.
            # Fingerprint is not unique in DB (legacy dupes possible) — never use one_or_none().
            fp = content_fingerprint(
                normalize_text(
                    f"{item.title}. {item.text}" if item.title else item.text
                )
            )
            fp_exists = (
                self.db.query(RawItem.id)
                .filter(RawItem.content_fingerprint == fp)
                .limit(1)
                .first()
            )
            if fp_exists:
                continue

            row = RawItem(
                provider=item.provider.value,
                external_id=item.external_id,
                url=item.url,
                author=item.author,
                title=item.title,
                text=item.text,
                language=item.language,
                published_at=item.published_at,
                fetched_at=item.fetched_at,
                raw_payload=item.raw_payload,
                content_fingerprint=fp,
            )
            self.db.add(row)
            inserted += 1
        self.db.commit()
        return inserted

    def unprocessed(self, limit: int = 100) -> list[RawItem]:
        return (
            self.db.query(RawItem)
            .filter(RawItem.processed == 0)
            .order_by(RawItem.fetched_at.asc())
            .limit(limit)
            .all()
        )

    def mark_processed(self, raw_ids: list[str]) -> None:
        if not raw_ids:
            return
        (
            self.db.query(RawItem)
            .filter(RawItem.id.in_(raw_ids))
            .update({RawItem.processed: 1}, synchronize_session=False)
        )
        self.db.commit()


class EventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_cluster_key(self, cluster_key: str) -> Optional[Event]:
        return (
            self.db.query(Event)
            .filter(Event.cluster_key == cluster_key)
            .one_or_none()
        )

    def upsert_from_cluster(
        self,
        *,
        cluster_key: str,
        title: str,
        related_symbols: list[str],
        related_sectors: list[str],
        providers: list[str],
        raw_ids: list[str],
    ) -> Event:
        event = self.get_by_cluster_key(cluster_key)
        if event is None:
            event = Event(
                cluster_key=cluster_key,
                title=title,
                status="open",
                related_symbols=related_symbols,
                related_sectors=related_sectors,
                providers=providers,
                raw_item_count=len(raw_ids),
            )
            self.db.add(event)
            self.db.flush()
        else:
            event.title = title or event.title
            event.status = "updated"
            event.updated_at = datetime.utcnow()
            event.related_symbols = related_symbols or event.related_symbols
            event.related_sectors = related_sectors or event.related_sectors
            event.providers = list(dict.fromkeys((event.providers or []) + providers))
            event.raw_item_count = (event.raw_item_count or 0) + len(raw_ids)

        existing_raw = {
            link.raw_item_id
            for link in (
                self.db.query(EventRawItem)
                .filter(EventRawItem.event_id == event.id)
                .all()
            )
        }
        for rid in raw_ids:
            if rid in existing_raw:
                continue
            self.db.add(EventRawItem(event_id=event.id, raw_item_id=rid))

        self.db.commit()
        self.db.refresh(event)
        return event


class SignalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_recent(self, limit: int = 20, symbol: Optional[str] = None) -> list[Signal]:
        q = (
            self.db.query(Signal)
            .filter(Signal.status == "published")
            .order_by(Signal.updated_at.desc())
        )
        if symbol:
            rows = q.limit(limit * 5).all()
            filtered = [r for r in rows if symbol in (r.related_symbols or [])]
            return filtered[:limit]
        return q.limit(limit).all()

    def list_recent_for_home(
        self, limit: int = 40, *, since: Optional[datetime] = None
    ) -> list[Signal]:
        """Published signals ordered by source/publish time for the home feed."""
        published = func.coalesce(
            Signal.published_at,
            Signal.first_seen_at,
            Signal.updated_at,
        )
        q = self.db.query(Signal).filter(Signal.status == "published")
        if since is not None:
            q = q.filter(published >= since)
        return q.order_by(published.desc()).limit(limit).all()

    def get(self, signal_id: str) -> Optional[Signal]:
        return self.db.query(Signal).filter(Signal.id == signal_id).one_or_none()

    def save(self, signal: Signal) -> Signal:
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        return signal

    def count_published_today(self) -> int:
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(Signal)
            .filter(
                Signal.status == "published",
                Signal.first_seen_at >= start,
            )
            .count()
        )

    def count_issue_cards_today(self) -> int:
        """Draft + published created today — used for daily soft/hard create caps."""
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(Signal)
            .filter(
                Signal.status.in_(("draft", "published")),
                Signal.first_seen_at >= start,
            )
            .count()
        )

    def count_published_today_for_symbol(self, symbol: str) -> int:
        """Published today whose related_symbols include this ticker."""
        sym = symbol.upper()
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = (
            self.db.query(Signal)
            .filter(
                Signal.status == "published",
                Signal.first_seen_at >= start,
            )
            .all()
        )
        return sum(1 for r in rows if sym in [x.upper() for x in (r.related_symbols or [])])

    def remaining_daily_quota(self, daily_cap: int) -> int:
        return max(0, daily_cap - self.count_published_today())

    def count_published_for_symbol(self, symbol: str, limit_scan: int = 200) -> int:
        """Count published signals whose related_symbols include this ticker."""
        sym = symbol.upper()
        rows = (
            self.db.query(Signal)
            .filter(Signal.status == "published")
            .order_by(Signal.updated_at.desc())
            .limit(limit_scan)
            .all()
        )
        return sum(1 for r in rows if sym in (r.related_symbols or []))


class WatchlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_user(self, user_id: str) -> list[WatchlistItem]:
        from sqlalchemy.orm import joinedload

        return (
            self.db.query(WatchlistItem)
            .options(joinedload(WatchlistItem.asset))
            .filter(WatchlistItem.user_id == user_id)
            .all()
        )

    def add(self, user_id: str, asset_id: str) -> WatchlistItem:
        existing = (
            self.db.query(WatchlistItem)
            .filter(
                WatchlistItem.user_id == user_id,
                WatchlistItem.asset_id == asset_id,
            )
            .one_or_none()
        )
        if existing:
            return existing
        item = WatchlistItem(user_id=user_id, asset_id=asset_id)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_by_symbol(self, user_id: str, symbol: str) -> bool:
        """Delete watchlist row for symbol. Returns True if a row was removed."""
        from sqlalchemy.orm import joinedload

        sym = symbol.upper().strip()
        rows = (
            self.db.query(WatchlistItem)
            .options(joinedload(WatchlistItem.asset))
            .filter(WatchlistItem.user_id == user_id)
            .all()
        )
        target = next(
            (r for r in rows if r.asset and r.asset.symbol.upper() == sym),
            None,
        )
        if not target:
            return False
        self.db.delete(target)
        self.db.commit()
        return True


class CursorRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, provider: str, cursor_key: str) -> Optional[str]:
        row = (
            self.db.query(IngestCursor)
            .filter(
                IngestCursor.provider == provider,
                IngestCursor.cursor_key == cursor_key,
            )
            .one_or_none()
        )
        return row.cursor_value if row else None

    def set(self, provider: str, cursor_key: str, cursor_value: str) -> None:
        row = (
            self.db.query(IngestCursor)
            .filter(
                IngestCursor.provider == provider,
                IngestCursor.cursor_key == cursor_key,
            )
            .one_or_none()
        )
        if row:
            row.cursor_value = cursor_value
            row.updated_at = datetime.utcnow()
        else:
            self.db.add(
                IngestCursor(
                    provider=provider,
                    cursor_key=cursor_key,
                    cursor_value=cursor_value,
                )
            )
        self.db.commit()


class MacroEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_many(self, items: list[MacroCalendarItem]) -> tuple[int, int]:
        """Insert or refresh rows. Returns (inserted, updated)."""
        inserted = 0
        updated = 0
        for item in items:
            row = (
                self.db.query(MacroEvent)
                .filter(
                    MacroEvent.provider == item.provider,
                    MacroEvent.external_id == item.external_id,
                )
                .one_or_none()
            )
            if row:
                row.title = item.title
                row.category = item.category
                row.event_date = item.event_date
                row.event_at = item.event_at
                row.region = item.region
                row.importance = item.importance
                row.summary = item.summary
                row.source_agency = item.source_agency
                row.raw_payload = item.raw_payload
                row.updated_at = datetime.utcnow()
                updated += 1
            else:
                self.db.add(
                    MacroEvent(
                        provider=item.provider,
                        external_id=item.external_id,
                        title=item.title,
                        category=item.category,
                        event_date=item.event_date,
                        event_at=item.event_at,
                        region=item.region,
                        importance=item.importance,
                        summary=item.summary,
                        source_agency=item.source_agency,
                        raw_payload=item.raw_payload,
                    )
                )
                inserted += 1
        self.db.commit()
        return inserted, updated

    def list_between(
        self,
        *,
        date_from,
        date_to,
        limit: int | None = None,
    ) -> list[MacroEvent]:
        q = self.db.query(MacroEvent).filter(
            MacroEvent.event_date >= date_from,
            MacroEvent.event_date <= date_to,
        )
        q = q.order_by(MacroEvent.event_date.asc(), MacroEvent.importance.desc())
        if limit is not None and limit > 0:
            q = q.limit(limit)
        return q.all()

    def count(self) -> int:
        return self.db.query(MacroEvent).count()


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).one_or_none()

    def get_by_device_id(self, device_id: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.device_id == device_id.strip())
            .one_or_none()
        )

    def get_or_create_device(
        self,
        *,
        device_id: str,
        platform: str = "web",
        app_version: str | None = None,
    ) -> tuple[User, bool]:
        """Returns (user, created). Touches last_seen_at on every call."""
        did = device_id.strip()
        if not did:
            raise ValueError("device_id required")
        plat = (platform or "web").strip().lower()
        if plat not in {"ios", "android", "web"}:
            plat = "web"

        user = self.get_by_device_id(did)
        if user:
            user.last_seen_at = datetime.utcnow()
            user.platform = plat
            if app_version:
                user.app_version = app_version
            self.db.commit()
            self.db.refresh(user)
            return user, False

        user = User(
            device_id=did,
            platform=plat,
            app_version=app_version,
            plan_type="FREE",
            status="active",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user, True

    def set_display_name(self, user_id: str, display_name: str | None) -> User:
        user = self.get_by_id(user_id)
        if not user:
            raise ValueError("user not found")
        user.display_name = display_name
        self.db.commit()
        self.db.refresh(user)
        return user


class SubscriptionPaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def max_paid_expires_at(self, user_id: str) -> Optional[datetime]:
        rows = (
            self.db.query(SubscriptionPayment.expires_at)
            .filter(
                SubscriptionPayment.user_id == user_id,
                SubscriptionPayment.payment_status == "PAID",
                SubscriptionPayment.expires_at.isnot(None),
            )
            .all()
        )
        if not rows:
            return None
        return max(r[0] for r in rows if r[0] is not None)

    def upsert_payment(
        self,
        *,
        user_id: str,
        transaction_id: str,
        platform: str,
        expires_at: datetime,
        product_id: str,
        amount: float = 0.0,
        currency: str = "KRW",
        payment_status: str = "PAID",
        purchase_token: str | None = None,
        original_transaction_id: str | None = None,
        environment: str = "prod",
        raw_receipt: dict | None = None,
        payment_date: datetime | None = None,
    ) -> SubscriptionPayment:
        row = (
            self.db.query(SubscriptionPayment)
            .filter(
                SubscriptionPayment.platform == platform,
                SubscriptionPayment.transaction_id == transaction_id,
            )
            .one_or_none()
        )
        now = datetime.utcnow()
        if row:
            row.payment_status = payment_status
            row.expires_at = expires_at
            row.product_id = product_id
            row.amount = amount
            row.currency = currency
            row.purchase_token = purchase_token
            row.original_transaction_id = original_transaction_id
            row.environment = environment
            row.raw_receipt = raw_receipt
            row.last_verified_at = now
            self.db.commit()
            self.db.refresh(row)
            return row

        row = SubscriptionPayment(
            user_id=user_id,
            transaction_id=transaction_id,
            platform=platform,
            amount=amount,
            currency=currency,
            payment_status=payment_status,
            payment_date=payment_date or now,
            processed_at=now,
            expires_at=expires_at,
            product_id=product_id,
            purchase_token=purchase_token,
            original_transaction_id=original_transaction_id,
            environment=environment,
            raw_receipt=raw_receipt,
            last_verified_at=now,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
