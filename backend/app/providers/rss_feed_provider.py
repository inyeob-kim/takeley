"""Administrator RSS feeds — XML metadata only. Not ticker Google News."""

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

from app.domain.models import RawItem, SourceType
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
        self.timeout_seconds = timeout_seconds

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
        items = parse_rss_xml(
            response.text,
            feed_id=feed_id,
            language=language,
            limit=limit,
        )
        return RssFetchResult(
            items=items,
            status_code=response.status_code,
            etag=next_etag or etag,
            last_modified=next_modified or last_modified,
        )


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
        results.append(
            RawItem(
                provider=SourceType.NEWS,
                external_id=rss_external_id(feed_id, identity),
                url=link or None,
                author="rss",
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
                },
            )
        )
    return results
