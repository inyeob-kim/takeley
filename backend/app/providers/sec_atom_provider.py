"""SEC EDGAR current filings Atom → RawItem. Official US disclosures."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx

from app.domain.models import RawItem, SourceType
from app.providers.base import SourceProvider
from app.providers.http_headers import takeley_headers

_ATOM_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type={form}&owner=include&count=40&output=atom"
)
_MATERIAL_FORMS = ("8-K", "6-K", "S-1", "SC 13D")
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


class SecAtomProvider(SourceProvider):
    name = SourceType.OFFICIAL

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(
        self,
        *,
        query: Optional[str] = None,
        since_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[RawItem]:
        return self.fetch_material(limit=limit)

    def fetch_material(self, *, limit: int = 40) -> list[RawItem]:
        items: list[RawItem] = []
        per_form = max(8, limit // len(_MATERIAL_FORMS))
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for form in _MATERIAL_FORMS:
                try:
                    response = client.get(
                        _ATOM_URL.format(form=form),
                        headers=takeley_headers(),
                    )
                    response.raise_for_status()
                    items.extend(parse_sec_atom(response.text, limit=per_form, form=form))
                except Exception:
                    continue
        return items[:limit]


def is_routine_sec_title(title: str) -> bool:
    """Form 3/4/5 insider reports are not TAKELEY Issue material."""
    blob = f" {title.lower()} "
    if " 8-k" in blob or " 6-k" in blob or " s-1" in blob or " 13d" in blob:
        return False
    if blob.strip().startswith("4 -") or blob.strip().startswith("3 -") or blob.strip().startswith("5 -"):
        return True
    if "(reporting)" in blob and "8-k" not in blob:
        return True
    return False


def parse_sec_atom(xml_text: str, *, limit: int = 40, form: str | None = None) -> list[RawItem]:
    root = ET.fromstring(xml_text)
    entries = root.findall("a:entry", _ATOM_NS)
    if not entries:
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    results: list[RawItem] = []
    for entry in entries[:limit]:
        title = (
            entry.findtext("a:title", default="", namespaces=_ATOM_NS)
            or entry.findtext("{http://www.w3.org/2005/Atom}title")
            or ""
        ).strip()
        summary = (
            entry.findtext("a:summary", default="", namespaces=_ATOM_NS)
            or entry.findtext("{http://www.w3.org/2005/Atom}summary")
            or ""
        ).strip()
        atom_id = (
            entry.findtext("a:id", default="", namespaces=_ATOM_NS)
            or entry.findtext("{http://www.w3.org/2005/Atom}id")
            or ""
        ).strip()
        link_el = entry.find("a:link", _ATOM_NS) or entry.find(
            "{http://www.w3.org/2005/Atom}link"
        )
        link = (link_el.get("href") if link_el is not None else "") or ""
        updated = (
            entry.findtext("a:updated", default="", namespaces=_ATOM_NS)
            or entry.findtext("{http://www.w3.org/2005/Atom}updated")
            or ""
        ).strip()
        if not title or not atom_id:
            continue
        if is_routine_sec_title(title):
            continue
        published_at = None
        if updated:
            try:
                published_at = parsedate_to_datetime(updated)
                if published_at and published_at.tzinfo:
                    published_at = published_at.replace(tzinfo=None)
            except Exception:
                try:
                    published_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if published_at.tzinfo:
                        published_at = published_at.replace(tzinfo=None)
                except ValueError:
                    published_at = None
        text = f"{title}. {summary}".strip(" .")
        results.append(
            RawItem(
                provider=SourceType.OFFICIAL,
                external_id=atom_id[:255],
                url=link or None,
                author="SEC",
                title=title[:512],
                text=text,
                language="en",
                published_at=published_at,
                fetched_at=datetime.utcnow(),
                raw_payload={
                    "source": "sec_edgar",
                    "form": form,
                    "canonical_url": link or None,
                },
            )
        )
    return results
