"""News RSS provider — enrich with publisher article body when possible."""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import quote_plus

import httpx

from app.core.config import get_settings
from app.domain.models import RawItem, SourceType
from app.pipeline.normalize import is_relevant_to_symbol
from app.providers.article_fetch import fetch_article_body
from app.providers.base import SourceProvider

logger = logging.getLogger(__name__)


class NewsProvider(SourceProvider):
    name = SourceType.NEWS

    def __init__(
        self,
        rss_url: Optional[str] = None,
        *,
        locale: str = "en-US",
    ) -> None:
        settings = get_settings()
        self.rss_url = rss_url or settings.news_rss_url
        self.locale = (locale or "en-US").strip()
        self.fetch_body = bool(settings.news_fetch_body)
        self.body_timeout = float(settings.news_body_timeout_seconds)
        self.body_max_chars = int(settings.news_body_max_chars)
        self.body_min_chars = int(settings.news_body_min_chars)
        self.rss_parse_multiplier = max(1, int(settings.news_rss_parse_multiplier))
        self.body_scan_multiplier = max(1, int(settings.news_body_scan_multiplier))
        self.demo_fallback = bool(settings.news_demo_fallback)

    def _google_news_search_url(self, query: str) -> str:
        if self.locale.lower().startswith("ko"):
            return (
                "https://news.google.com/rss/search?"
                f"q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
            )
        return (
            "https://news.google.com/rss/search?"
            f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        )

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[RawItem]:
        url = self.rss_url
        if query and "news.google.com" in (self.rss_url or ""):
            url = self._google_news_search_url(query)

        # KR symbols stay zero-padded digits; US tickers uppercased.
        raw_sym = (symbol or "").strip()
        if raw_sym.isdigit():
            filter_symbol = raw_sym.zfill(6)
        else:
            filter_symbol = raw_sym.upper() if raw_sym else ""
        filter_name = name

        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Takeley/0.1"})
                resp.raise_for_status()
                items = self._parse_rss(
                    resp.text,
                    limit=max(limit * self.rss_parse_multiplier, 40),
                )
        except Exception:
            logger.exception("NewsProvider RSS fetch failed")
            if self.demo_fallback:
                logger.warning(
                    "news demo_fallback enabled; injecting demo items (not real articles)"
                )
                return self._demo_items(
                    query=query, symbol=filter_symbol, name=filter_name
                )[:limit]
            return []

        filtered: list[RawItem] = []
        for item in items:
            blob = f"{item.title or ''} {item.text}"
            if filter_symbol and not is_relevant_to_symbol(
                blob, filter_symbol, filter_name
            ):
                continue
            filtered.append(item)

        if not filtered:
            if not items and self.demo_fallback:
                logger.warning(
                    "news demo_fallback enabled; empty RSS channel → demo items"
                )
                return self._demo_items(
                    query=query, symbol=filter_symbol, name=filter_name
                )[:limit]
            return []

        # Never persist headline-only news — analyze invents facts without a body.
        if not self.fetch_body:
            logger.warning(
                "news skipped reason=fetch_body_disabled count=%s",
                len(filtered),
            )
            return []

        kept: list[RawItem] = []
        dropped = 0
        scan_cap = max(limit * self.body_scan_multiplier, limit)
        for item in filtered[:scan_cap]:
            enriched = self._enrich_with_body(item)
            if enriched is None:
                dropped += 1
                continue
            kept.append(enriched)
            if len(kept) >= limit:
                break

        logger.info(
            "news body enrich kept=%s dropped=%s candidates=%s",
            len(kept),
            dropped,
            len(filtered),
        )
        return kept

    def _enrich_with_body(self, item: RawItem) -> RawItem | None:
        """Return item with article body, or None if body cannot be extracted (do not store)."""
        rss_text = (item.text or "").strip()
        title = (item.title or "").strip()
        article = fetch_article_body(
            item.url or "",
            timeout=self.body_timeout,
            max_chars=self.body_max_chars,
            min_chars=self.body_min_chars,
        )
        if not article.ok:
            logger.warning(
                "news drop reason=no_body title=%s reason=%s url=%s",
                (title or "")[:80],
                article.reason,
                (item.url or "")[:160],
            )
            return None

        payload = dict(item.raw_payload or {})
        payload["rss_text"] = rss_text
        payload["body_ok"] = True
        payload["body_reason"] = article.reason
        if article.canonical_url:
            payload["canonical_url"] = article.canonical_url

        body = article.text.strip()
        # Keep headline for clustering context, then full body for analyze.
        combined = f"{title}\n\n{body}" if title and title not in body[:120] else body
        return item.model_copy(
            update={
                "text": combined,
                "url": article.canonical_url or item.url,
                "raw_payload": payload,
            }
        )

    def _parse_rss(self, xml_text: str, limit: int = 40) -> list[RawItem]:
        root = ET.fromstring(xml_text)
        channel_items = root.findall("./channel/item")
        if not channel_items:
            # Atom fallback
            ns = {"a": "http://www.w3.org/2005/Atom"}
            channel_items = root.findall("a:entry", ns)

        results: list[RawItem] = []
        for node in channel_items[:limit]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            if not link:
                link_el = node.find("link")
                if link_el is not None:
                    link = (link_el.get("href") or "").strip()
            description = (node.findtext("description") or "").strip()
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()
            guid = (node.findtext("guid") or link or title).strip()
            pub = node.findtext("pubDate") or node.findtext("published")
            published_at = None
            if pub:
                try:
                    published_at = parsedate_to_datetime(pub)
                except Exception:
                    published_at = None

            external_id = hashlib.sha256(guid.encode("utf-8")).hexdigest()[:32]
            text = f"{title}. {description}".strip()
            if not text:
                continue
            results.append(
                RawItem(
                    provider=SourceType.NEWS,
                    external_id=external_id,
                    url=link or None,
                    author="news",
                    title=title or None,
                    text=text,
                    language="en",
                    published_at=published_at,
                    fetched_at=datetime.utcnow(),
                    raw_payload={"guid": guid, "source": "rss"},
                )
            )
        return results

    def _demo_items(
        self,
        query: Optional[str] = None,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[RawItem]:
        now = datetime.utcnow()
        sym = (symbol or "MARKET").upper()
        label = name or sym
        samples = [
            (
                f"demo-news-{sym.lower()}-1",
                (
                    f"{label} ({sym}) is in focus after the latest US market update. "
                    f"Coverage discusses demand, pricing, and near-term catalysts for investors, "
                    f"while noting that results can still swing with rates and end-market spending. "
                    f"This demo item is for local offline testing only and is not a real article."
                ),
            ),
            (
                f"demo-news-{sym.lower()}-2",
                (
                    f"Analysts discuss the {label} outlook and guidance context for {sym}. "
                    f"Commentary covers revenue trajectory, margin sensitivity, and competitive "
                    f"positioning without introducing unverified price targets. This paragraph "
                    f"exists so local demo news is never headline-only when fallback is enabled."
                ),
            ),
        ]
        return [
            RawItem(
                provider=SourceType.NEWS,
                external_id=eid,
                url=f"https://example.com/news/{eid}",
                author="news-demo",
                title=text.split(",")[0][:80],
                text=text,
                language="en",
                published_at=now,
                fetched_at=now,
                raw_payload={
                    "demo": True,
                    "query": query,
                    "symbol": sym,
                    "body_ok": True,
                },
            )
            for eid, text in samples
        ]
