from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Iterable


_LEVEL_ALIASES = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def resolve_log_level(
    *,
    log_level: str = "",
    environment: str = "local",
    debug: bool = False,
) -> int:
    """
    Explicit LOG_LEVEL wins. Otherwise:
    - local / development / debug=True → DEBUG (상세)
    - else → INFO (운영 필수만)
    """
    explicit = (log_level or "").strip().upper()
    if explicit in _LEVEL_ALIASES:
        return _LEVEL_ALIASES[explicit]

    env = (environment or "").strip().lower()
    if debug or env in {"local", "dev", "development"}:
        return logging.DEBUG
    return logging.INFO


def configure_logging(level: int | None = None) -> int:
    """Configure root logging. Returns the effective level."""
    if level is None:
        try:
            from app.core.config import get_settings

            settings = get_settings()
            level = resolve_log_level(
                log_level=settings.log_level,
                environment=settings.environment,
                debug=settings.debug,
            )
        except Exception:
            level = logging.INFO

    root = logging.getLogger()
    # Avoid duplicate handlers when API + worker share process / re-import.
    if root.handlers:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )

    # Keep app/worker INFO visible — HTTP client DEBUG floods the terminal otherwise.
    for noisy in (
        "httpx",
        "httpcore",
        "hpack",
        "urllib3",
        "tweepy",
        "trafilatura",
        "charset_normalizer",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return level


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_now_iso() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def preview_text(text: str | None, limit: int = 100) -> str:
    raw = " ".join((text or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)] + "…"


def log_raw_items(
    logger: logging.Logger,
    items: Iterable[Any],
    *,
    context: str,
) -> None:
    """DEBUG-only item dump (provider / id / author / text preview)."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    seq = list(items)
    if not seq:
        logger.debug("%s items=0", context)
        return
    logger.debug("%s items=%s", context, len(seq))
    for idx, item in enumerate(seq, start=1):
        provider = getattr(item, "provider", None)
        provider_s = getattr(provider, "value", provider)
        logger.debug(
            "%s#%s provider=%s id=%s author=%s url=%s text=%s",
            context,
            idx,
            provider_s,
            getattr(item, "external_id", None),
            getattr(item, "author", None),
            getattr(item, "url", None),
            preview_text(getattr(item, "text", None) or getattr(item, "title", None)),
        )
