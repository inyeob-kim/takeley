"""Google Trends RSS → RawItem. News items under a query, XML only."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx

from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider
from app.providers.http_headers import takeley_headers
from app.providers.rss_feed_provider import _HTML_RE, _WS_RE, canonical_url

_TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"
_HT_NS = (
    "https://trends.google.com/trending/rss",
    "http://www.google.com/trends/hottrends",
)


class TrendsProvider(SourceProvider):
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
        return self.fetch_geo((query or "US").strip() or "US", limit=limit)

    def fetch_geo(self, geo: str, *, limit: int = 40) -> list[RawItem]:
        code = (geo or "US").strip().upper()
        url = _TRENDS_RSS.format(geo=code)
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers=takeley_headers())
            response.raise_for_status()
            xml_text = response.text
        return parse_trends_xml(xml_text, geo=code, limit=limit)


def _text(node: ET.Element | None, names: tuple[str, ...]) -> str:
    if node is None:
        return ""
    for name in names:
        found = node.find(name)
        if found is not None and (found.text or "").strip():
            return (found.text or "").strip()
        for ns in _HT_NS:
            found = node.find(f"{{{ns}}}{name}")
            if found is not None and (found.text or "").strip():
                return (found.text or "").strip()
    return ""


def _news_nodes(item: ET.Element) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    for ns in _HT_NS:
        nodes.extend(item.findall(f"{{{ns}}}news_item"))
    if not nodes:
        nodes = [child for child in list(item) if child.tag.endswith("news_item")]
    return nodes


def _external_id(geo: str, identity: str) -> str:
    return hashlib.sha256(f"{geo}:{identity}".encode("utf-8")).hexdigest()[:32]


def parse_trends_xml(xml_text: str, *, geo: str, limit: int = 40) -> list[RawItem]:
    root = ET.fromstring(xml_text)
    items_xml = root.findall("./channel/item")
    results: list[RawItem] = []
    for item in items_xml:
        query = (item.findtext("title") or "").strip()
        traffic = _text(item, ("approx_traffic",))
        news_nodes = _news_nodes(item)
        if news_nodes:
            for news in news_nodes:
                headline = _text(news, ("news_item_title", "title"))
                snippet = _text(news, ("news_item_snippet", "description"))
                link = _text(news, ("news_item_url", "link"))
                source = _text(news, ("news_item_source",))
                if not headline and not snippet:
                    continue
                snippet = _WS_RE.sub(" ", _HTML_RE.sub(" ", snippet)).strip()
                headline = _WS_RE.sub(" ", _HTML_RE.sub(" ", headline)).strip()
                canon = canonical_url(link) if link else ""
                identity = canon or f"{query}:{headline}"
                text = f"{headline}. {snippet}".strip(" .")
                if query and query.lower() not in text.lower():
                    text = f"{query}. {text}".strip(" .")
                if not text:
                    continue
                results.append(
                    RawItem(
                        provider=SourceType.NEWS,
                        external_id=_external_id(geo, identity),
                        url=link or None,
                        author=source or "trends",
                        title=headline or query,
                        text=text,
                        language="ko" if geo == "KR" else "en",
                        published_at=None,
                        fetched_at=datetime.utcnow(),
                        raw_payload={
                            "source": "search_trends",
                            "geo": geo,
                            "trend_query": query,
                            "approx_traffic": traffic or None,
                            "canonical_url": canon or None,
                        },
                    )
                )
                if len(results) >= limit:
                    return results
            continue
        if len(query) < 12:
            continue
        text = query if not traffic else f"{query}. Search interest {traffic}."
        results.append(
            RawItem(
                provider=SourceType.NEWS,
                external_id=_external_id(geo, query),
                url=None,
                author="trends",
                title=query,
                text=text,
                language="ko" if geo == "KR" else "en",
                fetched_at=datetime.utcnow(),
                raw_payload={
                    "source": "search_trends",
                    "geo": geo,
                    "trend_query": query,
                    "approx_traffic": traffic or None,
                },
            )
        )
        if len(results) >= limit:
            break
    return results
