"""NEWS card generation — short feed summary + longer detail body."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.pipeline.prompts import NEWS_CARD_PROMPT, NEWS_CARD_PROMPT_VERSION

logger = logging.getLogger(__name__)

_ALLOWED_CATEGORIES = frozenset(
    {"정치", "경제", "금융", "기술", "AI", "사회", "국제", "문화", "스포츠", "엔터"}
)


@dataclass
class NewsCard:
    title: str
    summary: str
    body: str = ""
    key_points: list[str] = field(default_factory=list)
    category: str | None = None
    source: str = "heuristic"  # heuristic | llm
    ok: bool = True
    reason: str = ""


def _clip(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _normalize_body(text: str, *, max_chars: int = 4500) -> str:
    """Keep markdown headings/bold and paragraph breaks; tidy whitespace."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in raw.split("\n")]
    out: list[str] = []
    blank = False
    for ln in lines:
        if not ln.strip():
            if out and not blank:
                out.append("")
                blank = True
            continue
        blank = False
        out.append(ln.strip())
    body = "\n".join(out).strip()
    if len(body) <= max_chars:
        return body
    cut = body[: max_chars - 1]
    # Prefer cutting at paragraph boundary
    if "\n\n" in cut:
        cut = cut.rsplit("\n\n", 1)[0]
    else:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"


def _heuristic_news(
    *,
    text: str,
    source_title: str | None,
    provider: str,
) -> NewsCard:
    title = (source_title or "").strip()
    body_src = (text or "").strip()
    if not title:
        title = re.split(r"[.!?\n]", body_src)[0].strip() or body_src[:80]
    title = _clip(title, 120)
    summary_src = body_src
    if source_title and body_src.lower().startswith(source_title.lower()):
        summary_src = body_src[len(source_title) :].lstrip(" .-:")
    summary = _clip(summary_src or title, 400)
    body = _normalize_body(summary_src or body_src, max_chars=2500)
    if len(title) < 4 or len(summary) < 8:
        return NewsCard(
            title=title or "",
            summary=summary or "",
            body=body,
            ok=False,
            reason="too_short",
            source="heuristic",
        )
    return NewsCard(
        title=title,
        summary=summary,
        body=body,
        key_points=[],
        category=None,
        source="heuristic",
        ok=True,
    )


def generate_news_card(
    *,
    text: str,
    provider: str,
    source_title: str | None = None,
    source_url: str | None = None,
) -> NewsCard:
    settings = get_settings()
    if not settings.openai_api_key:
        return _heuristic_news(
            text=text, source_title=source_title, provider=provider
        )
    try:
        from openai import OpenAI

        from app.core.usage import record_llm_usage

        client = OpenAI(api_key=settings.openai_api_key)
        # Full article body when available (RSS enrich); keep prompt bounded.
        prompt = NEWS_CARD_PROMPT.format(
            provider=provider or "unknown",
            source_title=(source_title or "")[:200] or "(none)",
            source_url=(source_url or "")[:500] or "(none)",
            text=(text or "")[:6000],
        )
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        record_llm_usage(resp, stage="news_generate", model=settings.openai_model)
        data = json.loads(resp.choices[0].message.content or "{}")
        title = str(data.get("title") or "").strip()
        summary = str(data.get("summary") or "").strip()
        body = _normalize_body(str(data.get("body") or ""))
        points_raw = data.get("key_points") or []
        if not isinstance(points_raw, list):
            points_raw = []
        key_points = [str(p).strip() for p in points_raw if str(p).strip()][:3]
        cat = data.get("category")
        category = None
        if cat is not None and str(cat).strip() in _ALLOWED_CATEGORIES:
            category = str(cat).strip()
        if len(title) < 4 or len(summary) < 8:
            fallback = _heuristic_news(
                text=text, source_title=source_title, provider=provider
            )
            if not fallback.ok:
                return NewsCard(
                    title=title,
                    summary=summary,
                    body=body,
                    ok=False,
                    reason="llm_too_short",
                    source="llm",
                )
            return fallback
        if len(body) < 80:
            # Prefer a readable detail body from source over a near-empty LLM body.
            heur = _heuristic_news(
                text=text, source_title=source_title, provider=provider
            )
            if len(heur.body) > len(body):
                body = heur.body
        return NewsCard(
            title=_clip(title, 200),
            summary=_clip(summary, 800),
            body=body,
            key_points=key_points,
            category=category,
            source="llm",
            ok=True,
        )
    except Exception:
        logger.exception(
            "news_generate llm failed version=%s; heuristic fallback",
            NEWS_CARD_PROMPT_VERSION,
        )
        return _heuristic_news(
            text=text, source_title=source_title, provider=provider
        )
