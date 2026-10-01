"""Fetch publisher article body after RSS (title-only feeds are insufficient)."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>\x00-\x1f]+", re.I)
_GNEWS_SIG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_GNEWS_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')
_BATCH_EXECUTE_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_BLOCKED_HOST_PARTS = (
    "news.google.",
    "google.com",
    "google.",
    "gstatic.com",
    "googleusercontent.com",
    "googlesyndication.com",
    "doubleclick.net",
    "schema.org",
    "w3.org",
)
_OG_IMAGE_RES = (
    re.compile(
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        re.I,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        re.I,
    ),
    re.compile(
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        re.I,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
        re.I,
    ),
)
_JSONLD_IMAGE_RE = re.compile(
    r'"image"\s*:\s*(?:"(https?://[^"]+)"|\[\s*"(https?://[^"]+)")',
    re.I,
)
_BAD_IMAGE_HINTS = (
    "1x1",
    "pixel",
    "spacer",
    "blank.",
    "favicon",
    "/logo",
    "sprite",
    "tracking",
    "doubleclick",
    "googlesyndication",
)


@dataclass(frozen=True)
class ArticleBody:
    text: str
    canonical_url: Optional[str]
    ok: bool
    reason: str = "ok"
    image_url: Optional[str] = None


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": _BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _strip_tracking(url: str) -> str:
    cleaned = re.split(r"[\x00-\x1f]", url, maxsplit=1)[0]
    return cleaned.rstrip(").,;]'\"")


def _is_publisher_host(host: str) -> bool:
    h = (host or "").lower()
    if not h:
        return False
    return not any(part in h for part in _BLOCKED_HOST_PARTS)


def _decode_google_news_article_id(article_id: str) -> Optional[str]:
    """Legacy ids sometimes embed a publisher URL in base64 (pre-2024)."""
    raw = article_id.strip().split("?")[0]
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
            if _is_publisher_host(host):
                return url
        ascii_runs = re.findall(rb"https?://[ -~]{12,}", decoded)
        for run in ascii_runs:
            try:
                url = _strip_tracking(run.decode("ascii", errors="ignore"))
            except Exception:
                continue
            host = (urlparse(url).hostname or "").lower()
            if _is_publisher_host(host):
                return url
    return None


def _google_news_article_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if "news.google." not in host:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    if parts[-2] not in {"articles", "read"} and not (
        len(parts) >= 3 and parts[-3] == "rss" and parts[-2] == "articles"
    ):
        # /rss/articles/ID or /articles/ID or /read/ID
        if "articles" not in parts and "read" not in parts:
            return None
    return parts[-1].split("?")[0] or None


def _resolve_google_news_batchexecute(
    url: str,
    *,
    client: httpx.Client,
) -> Optional[str]:
    """Post-2024 Google News ids are opaque — use the article-page batchexecute RPC."""
    article_id = _google_news_article_id(url)
    if not article_id:
        return None

    page_urls = (
        f"https://news.google.com/rss/articles/{article_id}",
        f"https://news.google.com/articles/{article_id}",
        url,
    )
    signature = timestamp = None
    for page_url in page_urls:
        try:
            page = client.get(page_url, headers=_browser_headers())
            html = page.text or ""
        except Exception:
            continue
        sig = _GNEWS_SIG_RE.search(html)
        ts = _GNEWS_TS_RE.search(html)
        if sig and ts and ts.group(1).isdigit():
            signature = sig.group(1)
            timestamp = ts.group(1)
            break
    if not signature or not timestamp:
        logger.info(
            "gnews resolve miss reason=no_signature article_id=%s",
            article_id[:40],
        )
        return None

    rpc_inner = json.dumps(
        [
            "garturlreq",
            [
                [
                    "X",
                    "X",
                    ["X", "X"],
                    None,
                    None,
                    1,
                    1,
                    "US:en",
                    None,
                    1,
                    None,
                    None,
                    None,
                    None,
                    None,
                    0,
                    1,
                ],
                "X",
                "X",
                1,
                [1, 1, 1],
                1,
                1,
                None,
                0,
                0,
                None,
                0,
            ],
            article_id,
            int(timestamp),
            signature,
        ],
        separators=(",", ":"),
    )
    f_req = json.dumps([[["Fbv4je", rpc_inner, None, "generic"]]], separators=(",", ":"))
    try:
        resp = client.post(
            _BATCH_EXECUTE_URL,
            headers={
                **_browser_headers(),
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Referer": "https://news.google.com/",
            },
            content=f"f.req={quote(f_req)}",
        )
        resp.raise_for_status()
        body = resp.text or ""
    except Exception:
        logger.info(
            "gnews resolve miss reason=batchexecute_http article_id=%s",
            article_id[:40],
            exc_info=True,
        )
        return None

    if body.startswith(")]}'"):
        body = body.split("\n", 1)[-1]
    # Response is often: <len>\n<json>
    lines = [ln for ln in body.split("\n") if ln.strip()]
    payload_text = None
    for ln in lines:
        if ln.strip().startswith("["):
            payload_text = ln.strip()
            break
    if not payload_text:
        return None
    try:
        envelopes = json.loads(payload_text)
        for env in envelopes:
            if (
                isinstance(env, list)
                and len(env) >= 3
                and env[0] == "wrb.fr"
                and env[1] == "Fbv4je"
            ):
                inner = json.loads(env[2])
                if (
                    isinstance(inner, list)
                    and len(inner) >= 2
                    and inner[0] == "garturlres"
                    and isinstance(inner[1], str)
                ):
                    resolved = _strip_tracking(inner[1])
                    host = (urlparse(resolved).hostname or "").lower()
                    if _is_publisher_host(host):
                        logger.info(
                            "gnews resolve ok article_id=%s -> %s",
                            article_id[:40],
                            resolved[:160],
                        )
                        return resolved
    except Exception:
        logger.info(
            "gnews resolve miss reason=parse article_id=%s",
            article_id[:40],
            exc_info=True,
        )
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
    if "news.google." in host and (
        "/articles/" in parsed.path or "/read/" in parsed.path
    ):
        article_id = parsed.path.rstrip("/").split("/")[-1].split("?")[0]
        decoded = _decode_google_news_article_id(article_id)
        if decoded:
            return decoded
        batch = _resolve_google_news_batchexecute(url, client=client)
        if batch:
            return batch

    try:
        resp = client.get(url)
        final = str(resp.url)
        final_host = (urlparse(final).hostname or "").lower()
        if _is_publisher_host(final_host):
            return final
        for match in _HTTP_URL_RE.findall(resp.text or ""):
            cand = _strip_tracking(unquote(match))
            cand_host = (urlparse(cand).hostname or "").lower()
            if _is_publisher_host(cand_host):
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


def _is_usable_image_url(url: str) -> bool:
    raw = (url or "").strip()
    if not raw or raw.startswith("data:"):
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    path = (parsed.path or "").lower()
    blob = f"{host}{path}"
    if any(hint in blob for hint in _BAD_IMAGE_HINTS):
        return False
    return True


def extract_article_image(html: str, *, base_url: Optional[str] = None) -> Optional[str]:
    """Best-effort hero/OG image from publisher HTML. Never raises."""
    if not (html or "").strip():
        return None

    candidates: list[str] = []
    for rx in _OG_IMAGE_RES:
        for match in rx.finditer(html):
            candidates.append(unescape(match.group(1).strip()))
    for match in _JSONLD_IMAGE_RE.finditer(html):
        candidates.append(unescape((match.group(1) or match.group(2) or "").strip()))

    try:
        import trafilatura

        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            img = getattr(meta, "image", None) or getattr(meta, "image_url", None)
            if img:
                candidates.append(str(img).strip())
    except Exception:
        logger.debug("trafilatura metadata image failed", exc_info=True)

    base = base_url or ""
    for raw in candidates:
        if not raw:
            continue
        absolute = urljoin(base, raw)
        absolute = _strip_tracking(absolute)
        if _is_usable_image_url(absolute):
            return absolute[:1024]
    return None


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
    image_url = extract_article_image(html, base_url=canonical)
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
            image_url=image_url,
        )

    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0].strip()

    logger.info(
        "article_fetch ok url=%s chars=%s has_image=%s",
        canonical[:180],
        len(text),
        bool(image_url),
    )
    return ArticleBody(
        text=text,
        canonical_url=canonical,
        ok=True,
        reason="ok",
        image_url=image_url,
    )


def enrich_raw_item_with_body(
    item: "RawItem",
    *,
    timeout: float = 12.0,
    max_chars: int = 6000,
    min_chars: int = 280,
    log_prefix: str = "news",
) -> "RawItem | None":
    """Attach publisher article body to an RSS RawItem.

    Returns None when body cannot be extracted — callers MUST NOT persist
    headline/description-only items (facts get invented downstream).
    """
    from app.domain.models import RawItem  # local import avoids cycle

    if not isinstance(item, RawItem):
        return None

    rss_text = (item.text or "").strip()
    title = (item.title or "").strip()
    article = fetch_article_body(
        item.url or "",
        timeout=timeout,
        max_chars=max_chars,
        min_chars=min_chars,
    )
    if not article.ok:
        logger.warning(
            "%s drop reason=no_body title=%s reason=%s url=%s",
            log_prefix,
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
    if article.image_url:
        payload["image_url"] = article.image_url

    body = article.text.strip()
    # Keep headline for clustering context, then full body for analyze.
    combined = f"{title}\n\n{body}" if title and title not in body[:120] else body
    final_url = article.canonical_url or item.url
    # Prefer real publisher host over placeholder "rss"/"news" authors.
    from app.providers.rss_feed_provider import normalize_news_author

    author = normalize_news_author(item.author, url=final_url) or item.author
    if author and author != item.author:
        payload["publisher"] = author
    return item.model_copy(
        update={
            "text": combined,
            "url": final_url,
            "author": author,
            "raw_payload": payload,
        }
    )
