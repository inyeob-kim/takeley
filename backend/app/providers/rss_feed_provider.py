"""Administrator RSS feeds — parse XML, then fetch publisher article bodies."""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.config import get_settings
from app.domain.models import RawItem, SourceType
from app.providers.article_fetch import enrich_raw_item_with_body
from app.providers.base import SourceProvider

logger = logging.getLogger(__name__)

RSS_PAYLOAD_SOURCE = "rss_feed"
_TRACKING_QUERY = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
}
_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def canonical_url(url: str) -> str:
    """Strip common tracking query keys. Keep other query params."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_QUERY
    ]
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(kept, doseq=True),
            "",
        )
    )


def rss_external_id(feed_id: str, identity: str) -> str:
    return hashlib.sha256(f"{feed_id}:{identity}".encode("utf-8")).hexdigest()[:32]


_HOST_PUBLISHER_LABELS = {
    "bbc.co.uk": "BBC",
    "bbc.com": "BBC",
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "WSJ",
    "ft.com": "FT",
    "cnbc.com": "CNBC",
    "nytimes.com": "NYT",
    "theguardian.com": "Guardian",
    "apnews.com": "AP",
    "finance.yahoo.com": "Yahoo Finance",
    "yahoo.com": "Yahoo",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "washingtonpost.com": "Washington Post",
    "cnn.com": "CNN",
    "npr.org": "NPR",
    "forbes.com": "Forbes",
}


def publisher_label_from_url(url: str | None) -> str | None:
    """Human publisher label from article URL host (not Google News)."""
    raw = (url or "").strip()
    if not raw:
        return None
    host = (urlparse(raw).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or "news.google." in host or host == "news.google.com":
        return None
    for suffix, label in _HOST_PUBLISHER_LABELS.items():
        if host == suffix or host.endswith("." + suffix):
            return label
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3 and parts[-2] == "co":
        name = parts[-3]
    elif len(parts) >= 2:
        name = parts[-2]
    else:
        name = host
    return name.replace("-", " ").title() if name else None


_PLACEHOLDER_AUTHORS = frozenset({"rss", "news", "news-demo", "rss_feed"})


def rss_item_publisher(node: ET.Element, *, url: str | None = None) -> str:
    """Prefer RSS <source> text, else URL host label, else generic news."""
    source_el = node.find("source")
    if source_el is not None:
        name = (source_el.text or "").strip()
        if name:
            return name[:80]
    for tag in (
        "{http://purl.org/dc/elements/1.1/}creator",
        "{http://purl.org/dc/elements/1.1/}source",
    ):
        text = (node.findtext(tag) or "").strip()
        if text:
            return text[:80]
    return publisher_label_from_url(url) or "News"


def normalize_news_author(author: str | None, *, url: str | None = None) -> str | None:
    """Replace placeholder RSS authors with publisher label when possible."""
    raw = (author or "").strip() or None
    if raw and raw.lower() not in _PLACEHOLDER_AUTHORS:
        return raw
    return publisher_label_from_url(url) or (None if raw and raw.lower() in _PLACEHOLDER_AUTHORS else raw)


@dataclass
class RssFetchResult:
    items: list[RawItem]
    status_code: int
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    not_modified: bool = False


class RssFeedProvider(SourceProvider):
    name = SourceType.NEWS

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        settings = get_settings()
        self.timeout_seconds = timeout_seconds
        self.fetch_body = bool(settings.news_fetch_body)
        self.body_timeout = float(settings.news_body_timeout_seconds)
        self.body_max_chars = int(settings.news_body_max_chars)
        self.body_min_chars = int(settings.news_body_min_chars)

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        # Registry path uses fetch_feed. ABC fetch is unused.
        return []

    def fetch_feed(
        self,
        *,
        feed_id: str,
        url: str,
        language: str = "",
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        limit: int = 40,
    ) -> RssFetchResult:
        headers: dict[str, str] = {"User-Agent": "TAKELEY/1.0 (+https://takeley.co)"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
        next_etag = response.headers.get("etag")
        next_modified = response.headers.get("last-modified")
        if response.status_code == 304:
            return RssFetchResult(
                items=[],
                status_code=304,
                etag=next_etag or etag,
                last_modified=next_modified or last_modified,
                not_modified=True,
            )
        response.raise_for_status()
        parsed = parse_rss_xml(
            response.text,
            feed_id=feed_id,
            language=language,
            limit=limit,
        )
        items = self._enrich_feed_items(parsed)
        return RssFetchResult(
            items=items,
            status_code=response.status_code,
            etag=next_etag or etag,
            last_modified=next_modified or last_modified,
        )

    def _enrich_feed_items(self, items: list[RawItem]) -> list[RawItem]:
        """Fetch publisher HTML for each RSS item. Drop headline-only rows."""
        if not self.fetch_body:
            logger.warning(
                "rss_feed skipped body enrich reason=fetch_body_disabled count=%s",
                len(items),
            )
            return []

        kept: list[RawItem] = []
        dropped = 0
        for item in items:
            enriched = enrich_raw_item_with_body(
                item,
                timeout=self.body_timeout,
                max_chars=self.body_max_chars,
                min_chars=self.body_min_chars,
                log_prefix="rss_feed",
            )
            if enriched is None:
                dropped += 1
                continue
            kept.append(enriched)

        logger.info(
            "rss_feed body enrich kept=%s dropped=%s candidates=%s",
            len(kept),
            dropped,
            len(items),
        )
        return kept


def parse_rss_xml(
    xml_text: str,
    *,
    feed_id: str,
    language: str = "",
    limit: int = 40,
) -> list[RawItem]:
    root = ET.fromstring(xml_text)
    nodes = root.findall("./channel/item")
    if not nodes:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        nodes = root.findall("a:entry", ns)

    results: list[RawItem] = []
    for node in nodes[:limit]:
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not link:
            link_el = node.find("link")
            if link_el is not None:
                link = (link_el.get("href") or "").strip()
        description = (node.findtext("description") or node.findtext("summary") or "").strip()
        description = _WS_RE.sub(" ", _HTML_RE.sub(" ", description)).strip()
        guid = (node.findtext("guid") or node.findtext("{http://www.w3.org/2005/Atom}id") or "").strip()
        identity = guid or canonical_url(link)
        if not identity:
            continue
        pub = node.findtext("pubDate") or node.findtext("published") or node.findtext("updated")
        published_at = None
        if pub:
            try:
                published_at = parsedate_to_datetime(pub)
            except Exception:
                published_at = None
        text = f"{title}. {description}".strip(" .")
        if not text:
            continue
        canon = canonical_url(link) if link else ""
        publisher = rss_item_publisher(node, url=link or None)
        results.append(
            RawItem(
                provider=SourceType.NEWS,
                external_id=rss_external_id(feed_id, identity),
                url=link or None,
                author=publisher,
                title=title or None,
                text=text,
                language=(language or None),
                published_at=published_at,
                fetched_at=datetime.utcnow(),
                raw_payload={
                    "source": RSS_PAYLOAD_SOURCE,
                    "feed_id": feed_id,
                    "guid": guid or None,
                    "canonical_url": canon or None,
                    "publisher": publisher,
                },
            )
        )
    return results
