"""Fetch publisher article body after RSS (title-only feeds are insufficient)."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>\x00-\x1f]+", re.I)


@dataclass(frozen=True)
class ArticleBody:
    text: str
    canonical_url: Optional[str]
    ok: bool
    reason: str = "ok"


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _strip_tracking(url: str) -> str:
    cleaned = re.split(r"[\x00-\x1f]", url, maxsplit=1)[0]
    return cleaned.rstrip(").,;]'\"")


def _decode_google_news_article_id(article_id: str) -> Optional[str]:
    """Best-effort extract of publisher URL embedded in Google News article ids."""
    raw = article_id.strip()
    if not raw:
        return None
    pad = "=" * (-len(raw) % 4)
    candidates = [raw + pad, raw.replace("-", "+").replace("_", "/") + pad]
    for blob in candidates:
        try:
            decoded = base64.urlsafe_b64decode(blob)
        except Exception:
            continue
        try:
            as_text = decoded.decode("utf-8", errors="ignore")
        except Exception:
            as_text = ""
        for match in _HTTP_URL_RE.findall(as_text):
            url = _strip_tracking(unquote(match))
            host = (urlparse(url).hostname or "").lower()
            if host and "news.google." not in host and "google.com" not in host:
                return url
        ascii_runs = re.findall(rb"https?://[ -~]{12,}", decoded)
        for run in ascii_runs:
            try:
                url = _strip_tracking(run.decode("ascii", errors="ignore"))
            except Exception:
                continue
            host = (urlparse(url).hostname or "").lower()
            if host and "news.google." not in host and "google.com" not in host:
                return url
    return None


def resolve_publisher_url(
    url: str,
    *,
    client: httpx.Client,
) -> str:
    """Resolve Google News / redirectors to a publisher URL when possible."""
    if not url:
        return url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if "news.google." in host and "/articles/" in parsed.path:
        article_id = parsed.path.rstrip("/").split("/")[-1]
        decoded = _decode_google_news_article_id(article_id)
        if decoded:
            return decoded

    try:
        resp = client.get(url)
        final = str(resp.url)
        final_host = (urlparse(final).hostname or "").lower()
        if "news.google." not in final_host:
            return final
        for match in _HTTP_URL_RE.findall(resp.text or ""):
            cand = _strip_tracking(unquote(match))
            cand_host = (urlparse(cand).hostname or "").lower()
            if (
                cand_host
                and "news.google." not in cand_host
                and "google.com" not in cand_host
                and "gstatic.com" not in cand_host
            ):
                return cand
    except Exception:
        logger.debug("resolve_publisher_url failed url=%s", url, exc_info=True)
    return url


def extract_article_text(html: str, *, url: Optional[str] = None) -> str:
    try:
        import trafilatura

        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        return (text or "").strip()
    except Exception:
        logger.debug("trafilatura extract failed", exc_info=True)
        return ""


def fetch_article_body(
    url: str,
    *,
    timeout: float = 12.0,
    max_chars: int = 6000,
    min_chars: int = 280,
) -> ArticleBody:
    """
    Download publisher page and extract main article text.
    Fail soft: never raise. Caller MUST drop the item when ok=False
    (do not persist headline-only news).
    """
    if not (url or "").strip():
        return ArticleBody(text="", canonical_url=None, ok=False, reason="no_url")

    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=_browser_headers(),
        ) as client:
            resolved = resolve_publisher_url(url, client=client)
            try:
                resp = client.get(resolved)
                resp.raise_for_status()
            except Exception as exc:
                from app.core.usage import ARTICLE_HTTP_REQUESTS, record_usage

                record_usage(
                    ARTICLE_HTTP_REQUESTS,
                    1,
                    scope_type="shared",
                    tags={"ok": False},
                )
                logger.info(
                    "article_fetch fail reason=http url=%s err=%s",
                    resolved[:180],
                    type(exc).__name__,
                )
                return ArticleBody(
                    text="",
                    canonical_url=resolved,
                    ok=False,
                    reason="http_error",
                )
            from app.core.usage import ARTICLE_HTTP_REQUESTS, record_usage

            record_usage(
                ARTICLE_HTTP_REQUESTS,
                1,
                scope_type="shared",
                tags={"ok": True},
            )
            canonical = str(resp.url)
            html = resp.text or ""
    except Exception as exc:
        logger.info(
            "article_fetch fail reason=client url=%s err=%s",
            (url or "")[:180],
            type(exc).__name__,
        )
        return ArticleBody(text="", canonical_url=None, ok=False, reason="client_error")

    text = extract_article_text(html, url=canonical)
    if len(text) < min_chars:
        logger.info(
            "article_fetch fail reason=too_short url=%s chars=%s",
            canonical[:180],
            len(text),
        )
        return ArticleBody(
            text=text,
            canonical_url=canonical,
            ok=False,
            reason="too_short",
        )

    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].strip()

    logger.info(
        "article_fetch ok url=%s chars=%s",
        canonical[:180],
        len(text),
    )
    return ArticleBody(text=text, canonical_url=canonical, ok=True, reason="ok")
